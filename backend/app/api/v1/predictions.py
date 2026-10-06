"""Prediction engine API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import (
    assert_same_hospital_or_system_admin,
    require_permissions,
    require_roles,
)
from backend.app.auth.rbac import Permission
from backend.app.core.errors import NotFoundError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.prediction import Prediction
from backend.app.models.user import User
from backend.app.schemas.common import MessageResponse, Page, PaginationParams
from backend.app.schemas.prediction import (
    PredictionCreatedResponse,
    PredictionCreateRequest,
    PredictionPreviewRequest,
    PredictionRead,
    PredictionResponse,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.patient_service import PatientService
from backend.app.services.prediction_service import PredictionService

router = APIRouter()


def _response_from_result(
    *,
    result,
    model,
) -> PredictionResponse:
    return PredictionResponse(
        prediction=result.prediction,
        risk=result.risk,
        probability=result.probability,
        risk_level=result.risk_level,
        model_version=model.version,
        dataset_type=result.dataset_type,
        model_source=result.model_source,
        feature_names=result.feature_names,
        warnings=result.warnings,
    )


@router.post("/preview", response_model=PredictionResponse)
async def preview_prediction(
    payload: PredictionPreviewRequest,
    request: Request,
    current_user: User = Depends(require_permissions(Permission.CREATE_PREDICTION)),
    session: AsyncSession = Depends(get_db_session),
) -> PredictionResponse:
    """Run the active model against supplied features without persistence."""

    result, model = await PredictionService.predict_preview(session, payload)
    await AuditService.record(
        session,
        action="predictions.preview",
        user_id=current_user.id,
        resource_type="global_model",
        resource_id=str(model.id),
        details={
            "dataset_type": payload.dataset_type.value,
            "model_source": payload.model_source.value,
            "prediction": result.prediction,
            "probability": result.probability,
        },
        request=request,
    )
    return _response_from_result(result=result, model=model)


@router.post("", response_model=PredictionCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_prediction(
    payload: PredictionCreateRequest,
    request: Request,
    current_user: User = Depends(require_permissions(Permission.CREATE_PREDICTION)),
    session: AsyncSession = Depends(get_db_session),
) -> PredictionCreatedResponse:
    """Create and persist a prediction for a hospital-scoped patient."""

    patient = await PatientService.get_by_id(session, payload.patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    prediction, result, model = await PredictionService.create_for_patient(session, payload)
    await AuditService.record(
        session,
        action="predictions.create",
        user_id=current_user.id,
        resource_type="prediction",
        resource_id=str(prediction.id),
        details={
            "patient_id": str(prediction.patient_id),
            "model_version": model.version,
            "prediction": prediction.prediction,
            "probability": prediction.probability,
        },
        request=request,
    )
    base = _response_from_result(result=result, model=model)
    return PredictionCreatedResponse(
        **base.model_dump(),
        id=prediction.id,
        patient_id=prediction.patient_id,
        global_model_id=prediction.global_model_id,
        created_at=prediction.created_at,
    )


@router.get("", response_model=Page[PredictionRead])
async def list_predictions(
    params: PaginationParams = Depends(),
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> Page[PredictionRead]:
    """List persisted predictions inside the user's hospital scope."""

    scoped_hospital_id = (
        None if current_user.role == UserRole.SYSTEM_ADMIN else current_user.hospital_id
    )
    predictions, total = await PredictionService.list(
        session,
        offset=params.offset,
        limit=params.limit,
        hospital_id=scoped_hospital_id,
    )
    return Page(
        items=[PredictionRead.model_validate(prediction) for prediction in predictions],
        total=total,
        offset=params.offset,
        limit=params.limit,
    )


@router.get("/{prediction_id}", response_model=PredictionRead)
async def get_prediction(
    prediction_id: uuid.UUID,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PredictionRead:
    """Read a persisted prediction with hospital scoping."""

    prediction: Prediction | None = await PredictionService.get_by_id(session, prediction_id)
    if prediction is None:
        raise NotFoundError("Prediction")
    patient = await PatientService.get_by_id(session, prediction.patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    return PredictionRead.model_validate(prediction)


@router.delete("/{prediction_id}", response_model=MessageResponse)
async def delete_prediction(
    prediction_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Delete a persisted prediction inside the user's hospital scope."""

    prediction = await PredictionService.get_by_id(session, prediction_id)
    if prediction is None:
        raise NotFoundError("Prediction")
    patient = await PatientService.get_by_id(session, prediction.patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    deleted_prediction = await PredictionService.delete(session, prediction_id)
    await AuditService.record(
        session,
        action="predictions.delete",
        user_id=current_user.id,
        resource_type="prediction",
        resource_id=str(deleted_prediction.id),
        details={"patient_id": str(deleted_prediction.patient_id)},
        request=request,
    )
    return MessageResponse(message="Prediction deleted successfully")
