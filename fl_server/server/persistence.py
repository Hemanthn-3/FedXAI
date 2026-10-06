"""Persist federated rounds and activated models into the FedPedia database.

The Flower server writes through to the backend's SQLAlchemy models so the
analytics API, model registry, and prediction engine always reflect the real
federated lifecycle:

    active GlobalModel (round 0 seed) → TrainingRound per aggregated round →
    best round activated as the active GlobalModel after the run.

Every operation is fail-open: a database hiccup must never kill a training
run.  When ``database_url`` is unset the persistence object is a no-op, which
keeps unit tests and standalone Flower demos DB-free.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Columns on training_rounds guarded by CHECK constraints.
_UNIT_METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")


def to_sync_database_url(database_url: str) -> str:
    """Rewrite an async SQLAlchemy URL to its synchronous psycopg/sqlite form."""

    return (
        database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )


def _unit_metric(metrics: dict[str, Any], key: str) -> float | None:
    """Return a metric only if it is a finite number inside its DB constraint."""

    value = metrics.get(key)
    if value is None or isinstance(value, bool | bytes):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    if key == "loss":
        return number if number >= 0 else None
    return number if 0.0 <= number <= 1.0 else None


class FLPersistence:
    """Database bridge for the Flower server. No-op when unconfigured."""

    def __init__(
        self,
        database_url: str | None,
        *,
        dataset_type: str,
        total_clients: int,
        aggregation_strategy: str = "fedavg",
    ) -> None:
        self.dataset_type = dataset_type
        self.total_clients = total_clients
        self.aggregation_strategy = aggregation_strategy
        self.run_id = uuid.uuid4()
        self._session_factory: Any = None

        if not database_url:
            logger.info("FL persistence disabled (no DATABASE_URL).")
            return
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            engine = create_engine(
                to_sync_database_url(database_url),
                pool_pre_ping=True,
                future=True,
            )
            self._session_factory = sessionmaker(engine, expire_on_commit=False)
        except Exception as exc:  # pragma: no cover - driver import failures
            logger.warning("FL persistence disabled (engine creation failed): %s", exc)
            self._session_factory = None

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._session_factory is not None

    def _run(self, operation: Callable[[Any], _T], description: str) -> _T | None:
        if self._session_factory is None:
            return None
        try:
            with self._session_factory() as session:
                result = operation(session)
                session.commit()
                return result
        except Exception as exc:
            logger.warning("FL persistence: %s failed (fail-open): %s", description, exc)
            return None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def begin_run(self) -> None:
        """Start a fresh run: new run_id, clear prior round rows for this dataset."""

        def operation(session: Any) -> None:
            from sqlalchemy import delete

            from backend.app.models.enums import DatasetType
            from backend.app.models.training_round import TrainingRound

            session.execute(
                delete(TrainingRound).where(
                    TrainingRound.dataset_type == DatasetType(self.dataset_type)
                )
            )

        self._run(operation, "begin_run")

    def load_active_model_path(self) -> str | None:
        """Return the artifact path of the active federated GlobalModel, if any."""

        def operation(session: Any) -> str | None:
            from sqlalchemy import select

            from backend.app.models.enums import DatasetType, ModelSource
            from backend.app.models.global_model import GlobalModel

            row = session.execute(
                select(GlobalModel.path)
                .where(
                    GlobalModel.dataset_type == DatasetType(self.dataset_type),
                    GlobalModel.source == ModelSource.FEDERATED,
                    GlobalModel.is_active.is_(True),
                )
                .limit(1)
            ).scalar_one_or_none()
            return str(row) if row else None

        return self._run(operation, "load_active_model_path")

    def register_round(
        self,
        *,
        round_number: int,
        metrics: dict[str, Any],
        artifact_version: str | None = None,
        artifact_path: str | Path | None = None,
        artifact_checksum: str | None = None,
        status: str = "completed",
    ) -> None:
        """Persist one aggregated (or failed) round and its global model row."""

        def operation(session: Any) -> None:
            from backend.app.models.enums import (
                AggregationStrategy,
                DatasetType,
                ModelFramework,
                ModelSource,
                TrainingRoundStatus,
            )
            from backend.app.models.global_model import GlobalModel
            from backend.app.models.training_round import TrainingRound

            global_model_id: uuid.UUID | None = None
            if artifact_version and artifact_path and artifact_checksum:
                model = GlobalModel(
                    id=uuid.uuid4(),
                    version=artifact_version,
                    path=str(artifact_path),
                    checksum_sha256=str(artifact_checksum),
                    dataset_type=DatasetType(self.dataset_type),
                    framework=ModelFramework.PYTORCH,
                    source=ModelSource.FEDERATED,
                    metrics={
                        key: _unit_metric(metrics, key)
                        for key in (*_UNIT_METRICS, "loss")
                        if _unit_metric(metrics, key) is not None
                    },
                    is_active=False,
                )
                session.add(model)
                session.flush()
                global_model_id = model.id

            client_metrics = metrics.get("client_metrics")
            nodes = sorted(str(node) for node in client_metrics) if client_metrics else []
            participating = len(nodes) if status == "completed" else 0
            participating = min(participating, self.total_clients)

            now = datetime.now(UTC)
            session.add(
                TrainingRound(
                    run_id=self.run_id,
                    global_model_id=global_model_id,
                    round_number=round_number,
                    dataset_type=DatasetType(self.dataset_type),
                    aggregation_strategy=AggregationStrategy(self.aggregation_strategy),
                    status=TrainingRoundStatus(status),
                    total_clients=self.total_clients,
                    participating_clients=participating,
                    participating_nodes=nodes,
                    client_metrics=dict(client_metrics) if client_metrics else {},
                    accuracy=_unit_metric(metrics, "accuracy"),
                    precision=_unit_metric(metrics, "precision"),
                    recall=_unit_metric(metrics, "recall"),
                    f1=_unit_metric(metrics, "f1"),
                    roc_auc=_unit_metric(metrics, "roc_auc"),
                    loss=_unit_metric(metrics, "loss"),
                    completed_at=now if status in ("completed", "failed") else None,
                )
            )

        self._run(operation, f"register_round({round_number}, {status})")

    def activate_best(self) -> str | None:
        """Make the best federated model for this dataset the active one.

        Score = f1 + roc_auc - loss; ties go to the most recently created row.
        Returns the activated version, or None when nothing could be activated.
        """

        def operation(session: Any) -> str | None:
            from sqlalchemy import select

            from backend.app.models.enums import DatasetType, ModelSource
            from backend.app.models.global_model import GlobalModel

            rows = list(
                session.execute(
                    select(GlobalModel).where(
                        GlobalModel.dataset_type == DatasetType(self.dataset_type),
                        GlobalModel.source == ModelSource.FEDERATED,
                    )
                ).scalars()
            )
            if not rows:
                return None

            def score(model: GlobalModel) -> tuple[float, datetime]:
                stored = model.metrics or {}
                total = 0.0
                for key in ("f1", "roc_auc"):
                    value = _unit_metric(stored, key)
                    total += value if value is not None else 0.0
                loss = _unit_metric(stored, "loss")
                total -= loss if loss is not None else 0.0
                created = model.created_at or datetime.min.replace(tzinfo=UTC)
                return total, created

            best = max(rows, key=score)
            for model in rows:
                model.is_active = model.id == best.id
            logger.info(
                "FL persistence: activated model %s (score=%.4f)",
                best.version,
                score(best)[0],
            )
            return best.version

        return self._run(operation, "activate_best")
