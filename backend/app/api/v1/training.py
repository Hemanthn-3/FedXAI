"""Training monitor API — FL round status, live metrics, and admin controls."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_permissions
from backend.app.auth.rbac import Permission
from backend.app.core.errors import NotFoundError
from backend.app.database import get_db_session
from backend.app.models.enums import DatasetType, TrainingRoundStatus
from backend.app.models.global_model import GlobalModel
from backend.app.models.training_round import TrainingRound
from backend.app.models.user import User
from backend.app.services.model_service import ModelService

router = APIRouter()


def _global_model_payload(model: GlobalModel) -> dict[str, Any]:
    """Build API payload from DB row plus model artifact metadata."""

    input_dim: int | None = None
    feature_names: list[str] = []
    warnings: list[str] = []
    try:
        artifact = ModelService.load_artifact(
            path=model.path,
            dataset_type=model.dataset_type,
            expected_sha256=None,
        )
        input_dim = artifact.input_dim
        feature_names = list(artifact.feature_names)
        warnings = list(artifact.warnings)
    except Exception as exc:  # noqa: BLE001 - metadata should not hide the DB row
        warnings.append(f"Could not load artifact metadata: {exc}")

    metrics = model.metrics or {}
    client_metrics = metrics.get("client_metrics")
    participating_hospitals = (
        len(client_metrics)
        if isinstance(client_metrics, dict)
        else metrics.get("participating_clients")
    )

    return {
        "id": str(model.id),
        "version": model.version,
        "dataset_type": model.dataset_type.value,
        "source": model.source.value,
        "framework": model.framework.value,
        "path": model.path,
        "checksum_sha256": model.checksum_sha256,
        "is_active": model.is_active,
        "input_dim": input_dim,
        "feature_names": feature_names,
        "total_rounds": metrics.get("round_number"),
        "participating_hospitals": participating_hospitals,
        "metrics": metrics,
        "warnings": warnings,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


# ---------------------------------------------------------------------------
# Training rounds
# ---------------------------------------------------------------------------


@router.get("/rounds", summary="List FL training rounds")
async def list_training_rounds(
    dataset_type: DatasetType | None = Query(None),
    status: TrainingRoundStatus | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return a list of FL training rounds with per-round metrics."""
    from backend.app.services.analytics_service import AnalyticsService

    rounds = await AnalyticsService.list_rounds(session, dataset_type=dataset_type, limit=limit)
    return {
        "total": len(rounds),
        "offset": offset,
        "limit": limit,
        "rounds": rounds,
    }


@router.get("/rounds/{round_id}", summary="Get single training round")
async def get_training_round(
    round_id: uuid.UUID,
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return detailed metrics for a single training round."""
    r = await session.get(TrainingRound, round_id)
    if r is None:
        raise NotFoundError("Training round")
    return {
        "id": str(r.id),
        "run_id": str(r.run_id),
        "round_number": r.round_number,
        "dataset_type": r.dataset_type.value,
        "aggregation_strategy": r.aggregation_strategy.value,
        "status": r.status.value,
        "accuracy": r.accuracy,
        "precision": r.precision,
        "recall": r.recall,
        "f1": r.f1,
        "roc_auc": r.roc_auc,
        "loss": r.loss,
        "participating_clients": r.participating_clients,
        "total_clients": r.total_clients,
        "participating_nodes": r.participating_nodes,
        "client_metrics": r.client_metrics,
        "global_model_id": str(r.global_model_id) if r.global_model_id else None,
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


# ---------------------------------------------------------------------------
# Global models
# ---------------------------------------------------------------------------


@router.get("/models", summary="List global model artifacts")
async def list_global_models(
    dataset_type: DatasetType | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Return all registered global model artifacts."""
    stmt = select(GlobalModel).order_by(GlobalModel.created_at.desc()).limit(limit)
    if dataset_type is not None:
        stmt = stmt.where(GlobalModel.dataset_type == dataset_type)
    result = await session.execute(stmt)
    models = result.scalars().all()
    return [_global_model_payload(m) for m in models]


@router.get("/models/active", summary="Get the active global model")
async def get_active_model(
    dataset_type: DatasetType = Query(DatasetType.HEART_DISEASE),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the currently active global model for a dataset type."""
    stmt = (
        select(GlobalModel)
        .where(
            GlobalModel.dataset_type == dataset_type,
            GlobalModel.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    m = result.scalar_one_or_none()
    if m is None:
        raise NotFoundError("Active global model")
    return _global_model_payload(m)


# ---------------------------------------------------------------------------
# Hospital / node status
# ---------------------------------------------------------------------------


@router.get("/nodes", summary="Hospital node status summary")
async def node_status(
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.MONITOR_HOSPITAL_NODE)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Return status of all hospital nodes (hospital records)."""
    from backend.app.models.hospital import Hospital  # avoid circular at module level

    result = await session.execute(
        select(Hospital).order_by(Hospital.name)
    )
    hospitals = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "name": h.name,
            "location": h.location,
            "node_id": h.node_id,
            "status": h.status.value,
        }
        for h in hospitals
    ]


# ---------------------------------------------------------------------------
# Admin FL controls (system-admin only)
# ---------------------------------------------------------------------------


@router.post("/rounds/{round_id}/cancel", summary="Cancel a running training round")
async def cancel_training_round(
    round_id: uuid.UUID,
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.CONTROL_FL_ROUNDS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark a RUNNING or PENDING round as CANCELLED.

    Advisory only: this updates the database record shown in the UI. The Flower
    server runs independently (there is no control channel from the API to a
    live Flower run), so a round already executing on the FL server is not
    interrupted. Rounds are registered by the FL server only when they actually
    complete or fail, so CANCELLED rows are typically stale PENDING records.
    """
    r = await session.get(TrainingRound, round_id)
    if r is None:
        raise NotFoundError("Training round")
    if r.status not in {TrainingRoundStatus.RUNNING, TrainingRoundStatus.PENDING}:
        return {
            "round_id": str(round_id),
            "status": r.status.value,
            "message": "Round is not in a cancellable state",
        }
    r.status = TrainingRoundStatus.CANCELLED
    await session.flush()
    return {
        "round_id": str(round_id),
        "status": r.status.value,
        "message": (
            "Training round marked cancelled in the database "
            "(advisory — a live Flower run is not interrupted)"
        ),
    }
