"""Explainable AI report request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.models.enums import XAIStatus
from backend.app.schemas.common import ORMModel


class XAIGenerateRequest(BaseModel):
    regenerate: bool = False
    background_size: int = Field(default=48, ge=8, le=256)


class XAIReportRead(ORMModel):
    id: uuid.UUID
    prediction_id: uuid.UUID
    shap_path: str | None
    lime_path: str | None
    feature_ranking: list[dict]
    local_contributions: list[dict]
    status: XAIStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class XAIReportResponse(XAIReportRead):
    top_shap_features: list[str] = Field(default_factory=list)
    top_lime_features: list[str] = Field(default_factory=list)
