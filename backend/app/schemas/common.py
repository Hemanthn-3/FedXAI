"""Shared API schema primitives."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base class for schemas created from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0, le=100_000)
    limit: int = Field(default=50, ge=1, le=200)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    message: str


class IDResponse(BaseModel):
    id: uuid.UUID


class TimestampedModel(ORMModel):
    created_at: datetime
    updated_at: datetime | None = None
