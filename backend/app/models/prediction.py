"""Persisted healthcare prediction and provenance."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import (
    DatasetType,
    ModelSource,
    RiskLevel,
    enum_values,
)

if TYPE_CHECKING:
    from backend.app.models.global_model import GlobalModel
    from backend.app.models.patient import Patient
    from backend.app.models.xai_report import XAIReport


class Prediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("probability BETWEEN 0 AND 1", name="probability_unit"),
        CheckConstraint("prediction IN (0, 1)", name="prediction_binary"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    global_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("global_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dataset_type: Mapped[DatasetType] = mapped_column(
        Enum(DatasetType, name="dataset_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    model_source: Mapped[ModelSource] = mapped_column(
        Enum(ModelSource, name="model_source", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    input_features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    prediction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="predictions")
    global_model: Mapped["GlobalModel | None"] = relationship(back_populates="predictions")
    xai_report: Mapped["XAIReport | None"] = relationship(
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Prediction(id={self.id!s}, prediction={self.prediction}, "
            f"probability={self.probability:.4f})"
        )
