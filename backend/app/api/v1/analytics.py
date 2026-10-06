"""Analytics API endpoints — FL metrics, comparison, fairness, node participation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from analytics.fairness import (
    FairnessReportBuilder,
    FeatureInfluenceComparison,
    GroupFairnessAnalysis,
)
from backend.app.auth.dependencies import require_permissions
from backend.app.auth.rbac import Permission
from backend.app.database import get_db_session
from backend.app.models.enums import DatasetType
from backend.app.models.user import User
from backend.app.services.analytics_service import AnalyticsService

router = APIRouter()


# ---------------------------------------------------------------------------
# FL Metrics
# ---------------------------------------------------------------------------


@router.get("/fl/report", summary="Full FL analytics report")
async def fl_report(
    dataset_type: DatasetType | None = Query(None, description="Filter by dataset type"),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return full FL analytics: accuracy/loss/F1 series, node participation."""
    return await AnalyticsService.fl_report(session, dataset_type=dataset_type)


@router.get("/fl/rounds", summary="Training round list")
async def fl_rounds(
    dataset_type: DatasetType | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List individual training rounds with per-round metrics."""
    return await AnalyticsService.list_rounds(
        session, dataset_type=dataset_type, limit=limit
    )


@router.get("/fl/nodes", summary="Hospital node participation")
async def node_participation(
    dataset_type: DatasetType | None = Query(None),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return per-node participation counts and rates."""
    return await AnalyticsService.node_participation(session, dataset_type=dataset_type)


# ---------------------------------------------------------------------------
# FL vs Centralized Comparison
# ---------------------------------------------------------------------------


@router.get("/comparison", summary="FL vs centralized learning comparison")
async def comparison_report(
    dataset_type: DatasetType | None = Query(None),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.COMPARE_MODELS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Compare federated and centralized metrics side-by-side."""
    return await AnalyticsService.comparison_report(session, dataset_type=dataset_type)


# ---------------------------------------------------------------------------
# Prediction Statistics
# ---------------------------------------------------------------------------


@router.get("/predictions/stats", summary="Prediction statistics")
async def prediction_stats(
    dataset_type: DatasetType | None = Query(None),
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.VIEW_METRICS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Aggregated prediction counts, positive rate, and average probability."""
    return await AnalyticsService.prediction_stats(session, dataset_type=dataset_type)


# ---------------------------------------------------------------------------
# Fairness Analysis
# ---------------------------------------------------------------------------


def _group_label(feature: str, raw: Any) -> str:
    """Map a raw input feature value to a demographic group label."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if feature == "sex":
        return "male" if value == 1.0 else "female"
    if value == int(value):
        return str(int(value))
    return str(value)


async def _groups_from_db(session: AsyncSession, feature_name: str) -> dict[str, Any]:
    """Build demographic groups from real stored predictions (no labels)."""
    from sqlalchemy import select

    from backend.app.models.prediction import Prediction

    stmt = select(Prediction).order_by(Prediction.created_at.desc()).limit(500)
    preds = (await session.execute(stmt)).scalars().all()

    grouped: dict[str, list[int]] = {}
    for p in preds:
        feats = p.input_features or {}
        if feature_name not in feats:
            continue
        label = _group_label(feature_name, feats[feature_name])
        grouped.setdefault(label, []).append(int(p.prediction))

    return {
        label: {
            "predictions": values,
            "positive_rate": round(sum(values) / len(values), 4),
        }
        for label, values in grouped.items()
    }


async def _rankings_from_xai(
    session: AsyncSession,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Derive federated/centralized feature rankings from stored XAI reports."""
    from sqlalchemy import select

    from backend.app.models.prediction import Prediction
    from backend.app.models.xai_report import XAIReport

    stmt = (
        select(Prediction.model_source, XAIReport.feature_ranking)
        .join(XAIReport, XAIReport.prediction_id == Prediction.id)
        .order_by(XAIReport.created_at.desc())
        .limit(50)
    )
    rows = (await session.execute(stmt)).all()

    totals: dict[str, dict[str, float]] = {"federated": {}, "centralized": {}}
    for source, ranking in rows:
        bucket = totals.get(str(source.value if hasattr(source, "value") else source))
        if not bucket or not ranking:
            continue
        for item in ranking:
            feature = item.get("feature")
            if not feature:
                continue
            try:
                score = abs(float(item.get("abs_contribution", item.get("contribution", 0.0))))
            except (TypeError, ValueError):
                continue
            bucket[str(feature)] = bucket.get(str(feature), 0.0) + score

    def top(bucket: dict[str, float]) -> list[dict[str, Any]]:
        return [
            {"feature": f, "abs_contribution": round(s, 6)}
            for f, s in sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)
        ]

    return top(totals["federated"]), top(totals["centralized"])


@router.post(
    "/fairness",
    summary="Run fairness analysis on real stored predictions",
)
async def fairness_analysis(
    payload: dict[str, Any],
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.ANALYZE_FAIRNESS)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Group-level fairness analysis built from real stored predictions.

    The caller only supplies ``feature_name`` and ``privileged_group``; groups
    are computed server-side from Prediction rows. Feature influence rankings
    come from stored XAI reports. With no recorded ground truth, label-dependent
    metrics (equalized odds, accuracy) are omitted rather than faked.
    """
    feature_name: str = str(payload.get("feature_name", "sex"))
    privileged_group: str = str(payload.get("privileged_group", "male"))
    supplied_groups: dict[str, Any] = payload.get("groups") or {}
    fl_ranking: list[dict[str, Any]] = payload.get("federated_ranking") or []
    cl_ranking: list[dict[str, Any]] = payload.get("centralized_ranking") or []

    has_payload_data = any(
        bool(g.get("predictions")) for g in supplied_groups.values()
    )
    groups: dict[str, Any]
    if has_payload_data:
        groups = supplied_groups
    else:
        groups = await _groups_from_db(session, feature_name)

    if not fl_ranking or not cl_ranking:
        db_fl, db_cl = await _rankings_from_xai(session)
        fl_ranking = fl_ranking or db_fl
        cl_ranking = cl_ranking or db_cl

    builder = FairnessReportBuilder()

    if groups and privileged_group:
        analysis = GroupFairnessAnalysis(
            feature_name=feature_name,
            groups=groups,
            privileged_group=privileged_group,
        )
        builder.add_group_analysis(analysis)

    if fl_ranking and cl_ranking:
        comparison = FeatureInfluenceComparison(
            federated_ranking=fl_ranking,
            centralized_ranking=cl_ranking,
        )
        builder.set_feature_comparison(comparison)

    return builder.build(data_available=bool(groups))
