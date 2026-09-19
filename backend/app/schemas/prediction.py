"""Prediction request and response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.models.enums import DatasetType, ModelSource, RiskLevel
from backend.app.schemas.common import ORMModel

FeatureValue = int | float | str | bool


class PredictionFeaturePayload(BaseModel):
    features: dict[str, FeatureValue] = Field(min_length=1)

    @field_validator("features")
    @classmethod
    def normalize_feature_keys(
        cls,
        value: dict[str, FeatureValue],
    ) -> dict[str, FeatureValue]:
        normalized: dict[str, FeatureValue] = {}
        for key, feature_value in value.items():
            clean_key = key.strip().lower()
            if not clean_key:
                raise ValueError("Feature names cannot be empty")
            normalized[clean_key] = feature_value
        return normalized


class PredictionPreviewRequest(PredictionFeaturePayload):
    dataset_type: DatasetType = DatasetType.HEART_DISEASE
    model_source: ModelSource = ModelSource.FEDERATED


class PredictionCreateRequest(BaseModel):
    patient_id: uuid.UUID
    dataset_type: DatasetType = DatasetType.HEART_DISEASE
    model_source: ModelSource = ModelSource.FEDERATED
    features: dict[str, FeatureValue] | None = None
    doctor_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("features")
    @classmethod
    def normalize_optional_feature_keys(
        cls,
        value: dict[str, FeatureValue] | None,
    ) -> dict[str, FeatureValue] | None:
        if value is None:
            return None
        return PredictionFeaturePayload(features=value).features


class PredictionResponse(BaseModel):
    prediction: int
    risk: str
    probability: float
    risk_level: RiskLevel
    model_version: str
    dataset_type: DatasetType
    model_source: ModelSource
    feature_names: list[str]
    warnings: list[str] = Field(default_factory=list)


class PredictionRead(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    global_model_id: uuid.UUID | None
    dataset_type: DatasetType
    model_source: ModelSource
    input_features: dict[str, Any]
    probability: float
    risk_level: RiskLevel
    prediction: int
    doctor_notes: str | None
    created_at: datetime
    updated_at: datetime


class PredictionCreatedResponse(PredictionResponse):
    id: uuid.UUID
    patient_id: uuid.UUID
    global_model_id: uuid.UUID | None
    created_at: datetime
