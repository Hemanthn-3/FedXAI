"""Stored SHAP and LIME explanation artifacts."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import XAIStatus, enum_values

if TYPE_CHECKING:
    from backend.app.models.prediction import Prediction


class XAIReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "xai_reports"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    shap_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    lime_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    feature_ranking: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    local_contributions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    status: Mapped[XAIStatus] = mapped_column(
        Enum(XAIStatus, name="xai_status", values_callable=enum_values),
        nullable=False,
        default=XAIStatus.PENDING,
        server_default=XAIStatus.PENDING.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    prediction: Mapped["Prediction"] = relationship(back_populates="xai_report")

    def __repr__(self) -> str:
        return f"XAIReport(id={self.id!s}, status={self.status.value!r})"
