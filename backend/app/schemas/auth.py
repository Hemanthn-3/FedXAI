"""Authentication request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from backend.app.models.enums import UserRole
from backend.app.schemas.user import UserRead


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.DOCTOR
    hospital_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @model_validator(mode="after")
    def validate_hospital_scope(self) -> "RegisterRequest":
        if self.role in {UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN} and self.hospital_id is None:
            raise ValueError("hospital_id is required for hospital-scoped users")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_at: datetime


class AuthResponse(TokenPair):
    user: UserRead


class TokenPayload(BaseModel):
    sub: uuid.UUID
    typ: str
    role: UserRole
    sid: str
    jti: str
    permissions: list[str]
    hospital_id: uuid.UUID | None = None
    exp: int
    iat: int
    iss: str
    aud: str
