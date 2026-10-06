"""Prediction persistence and active-model inference service."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import NotFoundError
from backend.app.models.global_model import GlobalModel
from backend.app.models.patient import Patient
from backend.app.models.prediction import Prediction
from backend.app.schemas.prediction import PredictionCreateRequest, PredictionPreviewRequest
from backend.app.services.model_service import ModelService
from backend.app.services.patient_service import PatientService
from backend.app.services.prediction_engine import PredictionEngine, PredictionEngineResult


class PredictionService:
    """Coordinate model lookup, inference, and prediction persistence."""

    @staticmethod
    def patient_feature_payload(patient: Patient) -> dict[str, float | int]:
        """Build a feature payload using the exact canonical model feature names.

        Feature name mapping (Patient DB column → model feature name):
          bp          → trestbps
          cholesterol → chol
          heart_rate  → thalach
        All other columns map directly.
        """
        _log = logging.getLogger(__name__)

        features: dict[str, float | int] = {"age": patient.age}
        # Map patient DB columns to exact model feature names
        optional_values = {
            "sex":      patient.sex,
            "cp":       patient.cp,
            "trestbps": patient.bp,          # DB: bp → model: trestbps
            "chol":     patient.cholesterol,  # DB: cholesterol → model: chol
            "fbs":      patient.fbs,
            "thalach":  patient.heart_rate,   # DB: heart_rate → model: thalach
            "exang":    patient.exang,
            "oldpeak":  patient.oldpeak,
            # glucose/bmi kept under their own names for non-heart-disease models
            "glucose":  patient.glucose,
            "bmi":      patient.bmi,
        }
        for key, value in optional_values.items():
            if value is not None:
                features[key] = value

        _log.debug(
            "patient_feature_payload | patient_id=%s | features=%s",
            patient.id,
            features,
        )
        return features

    @staticmethod
    async def get_by_id(session: AsyncSession, prediction_id: uuid.UUID) -> Prediction | None:
        return await session.get(Prediction, prediction_id)

    @staticmethod
    async def delete(session: AsyncSession, prediction_id: uuid.UUID) -> Prediction:
        prediction = await PredictionService.get_by_id(session, prediction_id)
        if prediction is None:
            raise NotFoundError("Prediction")
        await session.delete(prediction)
        await session.flush()
        return prediction

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 50,
        hospital_id: uuid.UUID | None = None,
    ) -> tuple[list[Prediction], int]:
        filters = []
        statement = select(Prediction).join(Patient)
        count_statement = select(func.count()).select_from(Prediction).join(Patient)
        if hospital_id is not None:
            filters.append(Patient.hospital_id == hospital_id)
        total = int(await session.scalar(count_statement.where(*filters)) or 0)
        result = await session.execute(
            statement.where(*filters)
            .order_by(Prediction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def predict_preview(
        session: AsyncSession,
        payload: PredictionPreviewRequest,
    ) -> tuple[PredictionEngineResult, GlobalModel]:
        model = await ModelService.get_active_model(
            session,
            dataset_type=payload.dataset_type,
            source=payload.model_source,
        )
        artifact = ModelService.load_artifact(
            path=model.path,
            dataset_type=model.dataset_type,
            expected_sha256=None,  # already verified at registration
        )
        result = PredictionEngine.predict(
            artifact=artifact,
            features=payload.features,
            model_source=model.source,
        )
        return result, model

    @staticmethod
    async def create_for_patient(
        session: AsyncSession,
        payload: PredictionCreateRequest,
    ) -> tuple[Prediction, PredictionEngineResult, GlobalModel]:
        patient = await PatientService.get_by_id(session, payload.patient_id)
        if patient is None:
            raise NotFoundError("Patient")
        model = await ModelService.get_active_model(
            session,
            dataset_type=payload.dataset_type,
            source=payload.model_source,
        )
        features: dict[str, Any] = PredictionService.patient_feature_payload(patient)
        artifact = ModelService.load_artifact(
            path=model.path,
            dataset_type=model.dataset_type,
            expected_sha256=None,  # already verified at registration
        )
        result = PredictionEngine.predict(
            artifact=artifact,
            features=features,
            model_source=model.source,
        )
        logging.getLogger(__name__).info(
            "model_inference_completed | patient_id=%s | model_id=%s | model_version=%s | "
            "dataset_type=%s | source=%s | probability=%.6f | prediction=%d",
            patient.id,
            model.id,
            model.version,
            model.dataset_type.value,
            model.source.value,
            result.probability,
            result.prediction,
        )
        prediction = Prediction(
            patient_id=patient.id,
            global_model_id=model.id,
            dataset_type=model.dataset_type,
            model_source=model.source,
            input_features=result.normalized_features,
            probability=result.probability,
            risk_level=result.risk_level,
            prediction=result.prediction,
            doctor_notes=payload.doctor_notes,
        )
        session.add(prediction)
        await session.flush()
        await session.refresh(prediction)
        return prediction, result, model

    @staticmethod
    async def list_predictions(
        session: AsyncSession,
        *,
        hospital_id: uuid.UUID | None = None,
        limit: int = 500,
    ) -> list[Prediction]:
        """Flat list of predictions (no total count) for export paths."""
        rows, _ = await PredictionService.list(
            session,
            offset=0,
            limit=limit,
            hospital_id=hospital_id,
        )
        return rows
