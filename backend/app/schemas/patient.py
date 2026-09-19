"""Patient request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.common import ORMModel


class PatientBase(BaseModel):
    hospital_id: uuid.UUID | None = None
    external_reference: str | None = Field(default=None, max_length=120)
    age: int = Field(ge=0, le=130)
    sex: int | None = Field(default=None, ge=0, le=1)
    cp: int | None = Field(default=None, ge=0, le=4)
    bp: float | None = Field(default=None, ge=20, le=350)
    cholesterol: float | None = Field(default=None, ge=0, le=1500)
    glucose: float | None = Field(default=None, ge=0, le=1500)
    heart_rate: float | None = Field(default=None, ge=20, le=300)
    fbs: int | None = Field(default=None, ge=0, le=1)
    exang: int | None = Field(default=None, ge=0, le=1)
    oldpeak: float | None = Field(default=None, ge=0, le=10)
    bmi: float | None = Field(default=None, ge=5, le=150)
    target: int | None = Field(default=None, ge=0, le=1)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    external_reference: str | None = Field(default=None, max_length=120)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: int | None = Field(default=None, ge=0, le=1)
    cp: int | None = Field(default=None, ge=0, le=4)
    bp: float | None = Field(default=None, ge=20, le=350)
    cholesterol: float | None = Field(default=None, ge=0, le=1500)
    glucose: float | None = Field(default=None, ge=0, le=1500)
    heart_rate: float | None = Field(default=None, ge=20, le=300)
    fbs: int | None = Field(default=None, ge=0, le=1)
    exang: int | None = Field(default=None, ge=0, le=1)
    oldpeak: float | None = Field(default=None, ge=0, le=10)
    bmi: float | None = Field(default=None, ge=5, le=150)
    target: int | None = Field(default=None, ge=0, le=1)


class PatientRead(ORMModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    external_reference: str | None
    age: int
    sex: int | None
    cp: int | None
    bp: float | None
    cholesterol: float | None
    glucose: float | None
    heart_rate: float | None
    fbs: int | None
    exang: int | None
    oldpeak: float | None
    bmi: float | None
    target: int | None
    created_at: datetime
    updated_at: datetime
