"""Hospital request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.models.enums import HospitalStatus
from backend.app.schemas.common import ORMModel


class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=255)
    node_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    status: HospitalStatus = HospitalStatus.OFFLINE


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    location: str | None = Field(default=None, min_length=2, max_length=255)
    status: HospitalStatus | None = None


class HospitalRead(ORMModel):
    id: uuid.UUID
    name: str
    location: str
    node_id: str
    status: HospitalStatus
    created_at: datetime
    updated_at: datetime
