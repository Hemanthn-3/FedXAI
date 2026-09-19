"""Authenticated platform user."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import UserRole, enum_values

if TYPE_CHECKING:
    from backend.app.models.audit_log import AuditLog
    from backend.app.models.hospital import Hospital


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(name)) >= 2", name="name_min_length"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(
            "((role IN ('doctor', 'hospital_admin') AND hospital_id IS NOT NULL) "
            "OR (role IN ('system_admin', 'researcher')))",
            name="hospital_role_scope",
        ),
    )

    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    hospital: Mapped["Hospital | None"] = relationship(back_populates="users")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"User(id={self.id!s}, email={self.email!r}, role={self.role.value!r})"
