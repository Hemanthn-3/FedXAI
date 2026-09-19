"""Hospital tenant and federated-node identity."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import HospitalStatus, enum_values

if TYPE_CHECKING:
    from backend.app.models.patient import Patient
    from backend.app.models.user import User


class Hospital(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hospitals"
    __table_args__ = (
        CheckConstraint("length(trim(name)) >= 2", name="name_min_length"),
        CheckConstraint("length(trim(node_id)) >= 3", name="node_id_min_length"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    node_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    status: Mapped[HospitalStatus] = mapped_column(
        Enum(
            HospitalStatus,
            name="hospital_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=HospitalStatus.OFFLINE,
        server_default=HospitalStatus.OFFLINE.value,
        index=True,
    )

    users: Mapped[list["User"]] = relationship(back_populates="hospital")
    patients: Mapped[list["Patient"]] = relationship(back_populates="hospital")

    def __repr__(self) -> str:
        return f"Hospital(id={self.id!s}, node_id={self.node_id!r})"
