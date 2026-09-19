"""Federated training round metrics and participation record."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, UUIDPrimaryKeyMixin
from backend.app.models.enums import (
    AggregationStrategy,
    DatasetType,
    TrainingRoundStatus,
    enum_values,
)

if TYPE_CHECKING:
    from backend.app.models.global_model import GlobalModel


class TrainingRound(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "training_rounds"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "round_number",
            name="uq_training_rounds_run_round",
        ),
        CheckConstraint("round_number > 0", name="round_number_positive"),
        CheckConstraint("total_clients > 0", name="total_clients_positive"),
        CheckConstraint(
            "participating_clients BETWEEN 0 AND total_clients",
            name="participating_clients_valid",
        ),
        CheckConstraint("accuracy IS NULL OR accuracy BETWEEN 0 AND 1", name="accuracy_unit"),
        CheckConstraint("precision IS NULL OR precision BETWEEN 0 AND 1", name="precision_unit"),
        CheckConstraint("recall IS NULL OR recall BETWEEN 0 AND 1", name="recall_unit"),
        CheckConstraint("f1 IS NULL OR f1 BETWEEN 0 AND 1", name="f1_unit"),
        CheckConstraint("roc_auc IS NULL OR roc_auc BETWEEN 0 AND 1", name="roc_auc_unit"),
        CheckConstraint("loss IS NULL OR loss >= 0", name="loss_non_negative"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    global_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("global_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_type: Mapped[DatasetType] = mapped_column(
        Enum(DatasetType, name="dataset_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    aggregation_strategy: Mapped[AggregationStrategy] = mapped_column(
        Enum(
            AggregationStrategy,
            name="aggregation_strategy",
            values_callable=enum_values,
        ),
        nullable=False,
        default=AggregationStrategy.FEDAVG,
        server_default=AggregationStrategy.FEDAVG.value,
    )
    status: Mapped[TrainingRoundStatus] = mapped_column(
        Enum(
            TrainingRoundStatus,
            name="training_round_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=TrainingRoundStatus.PENDING,
        server_default=TrainingRoundStatus.PENDING.value,
        index=True,
    )
    total_clients: Mapped[int] = mapped_column(Integer, nullable=False)
    participating_clients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    participating_nodes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    client_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    global_model: Mapped["GlobalModel | None"] = relationship(back_populates="training_rounds")

    def __repr__(self) -> str:
        return (
            f"TrainingRound(run_id={self.run_id!s}, "
            f"round_number={self.round_number}, status={self.status.value!r})"
        )
