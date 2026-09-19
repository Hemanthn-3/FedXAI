"""Canonical patient features used for clinical prediction requests."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.encryption import EncryptedFloat
from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.hospital import Hospital
    from backend.app.models.prediction import Prediction


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("age BETWEEN 0 AND 130", name="age_valid"),
        # Note: bp, cholesterol, glucose, heart_rate, bmi are AES-256-GCM encrypted
        # ciphertext (Text columns) so range CheckConstraints are not applicable.
        CheckConstraint("target IS NULL OR target IN (0, 1)", name="target_binary"),
        UniqueConstraint(
            "hospital_id",
            "external_reference",
            name="uq_patients_hospital_external_reference",
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    age: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sex: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cp: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # ── PHI columns encrypted at rest using AES-256-GCM (EncryptedFloat) ───────
    bp: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    cholesterol: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    glucose: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    heart_rate: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    # ────────────────────────────────────────────────────────────
    fbs: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exang: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    oldpeak: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    target: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    hospital: Mapped["Hospital"] = relationship(back_populates="patients")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="patient")

    def __repr__(self) -> str:
        return f"Patient(id={self.id!s}, hospital_id={self.hospital_id!s})"
