"""User request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from backend.app.models.enums import UserRole
from backend.app.schemas.common import ORMModel


class UserBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: UserRole
    hospital_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @model_validator(mode="after")
    def validate_hospital_scope(self) -> "UserBase":
        if self.role in {UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN} and self.hospital_id is None:
            raise ValueError("hospital_id is required for hospital-scoped users")
        return self


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)
    is_active: bool = True


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: UserRole | None = None
    hospital_id: uuid.UUID | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_hospital_scope(self) -> "UserUpdate":
        if self.role in {UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN} and self.hospital_id is None:
            raise ValueError("hospital_id is required when assigning a hospital-scoped role")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserRead(ORMModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    hospital_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
