"""Versioned model artifact registry."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, Enum, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import (
    DatasetType,
    ModelFramework,
    ModelSource,
    enum_values,
)

if TYPE_CHECKING:
    from backend.app.models.prediction import Prediction
    from backend.app.models.training_round import TrainingRound


class GlobalModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "global_models"
    __table_args__ = (
        CheckConstraint("length(trim(version)) >= 1", name="version_not_blank"),
        CheckConstraint("length(checksum_sha256) = 64", name="checksum_sha256_length"),
        Index(
            "uq_global_models_active_dataset_source",
            "dataset_type",
            "source",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    version: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_type: Mapped[DatasetType] = mapped_column(
        Enum(DatasetType, name="dataset_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    framework: Mapped[ModelFramework] = mapped_column(
        Enum(ModelFramework, name="model_framework", values_callable=enum_values),
        nullable=False,
    )
    source: Mapped[ModelSource] = mapped_column(
        Enum(ModelSource, name="model_source", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    training_rounds: Mapped[list["TrainingRound"]] = relationship(back_populates="global_model")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="global_model")

    def __repr__(self) -> str:
        return f"GlobalModel(id={self.id!s}, version={self.version!r})"
