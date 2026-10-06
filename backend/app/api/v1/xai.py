"""Explainable AI report API endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import assert_same_hospital_or_system_admin, require_permissions
from backend.app.auth.rbac import Permission
from backend.app.core.errors import NotFoundError
from backend.app.database import get_db_session
from backend.app.models.user import User
from backend.app.schemas.xai import XAIGenerateRequest, XAIReportRead, XAIReportResponse
from backend.app.services.audit_service import AuditService
from backend.app.services.patient_service import PatientService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.xai_service import XAIService

router = APIRouter()


def _xai_response(report) -> XAIReportResponse:
    shap_features, lime_features = XAIService.top_features(report)
    base = XAIReportRead.model_validate(report)
    return XAIReportResponse(
        **base.model_dump(),
        top_shap_features=shap_features,
        top_lime_features=lime_features,
    )


async def _assert_prediction_scope(
    session: AsyncSession,
    *,
    prediction_id: uuid.UUID,
    current_user: User,
) -> None:
    prediction = await PredictionService.get_by_id(session, prediction_id)
    if prediction is None:
        raise NotFoundError("Prediction")
    patient = await PatientService.get_by_id(session, prediction.patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)


@router.post(
    "/predictions/{prediction_id}/reports",
    response_model=XAIReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_xai_report(
    prediction_id: uuid.UUID,
    payload: XAIGenerateRequest,
    request: Request,
    current_user: User = Depends(require_permissions(Permission.VIEW_EXPLANATIONS)),
    session: AsyncSession = Depends(get_db_session),
) -> XAIReportResponse:
    """Generate SHAP and LIME artifacts for a persisted prediction."""

    await _assert_prediction_scope(session, prediction_id=prediction_id, current_user=current_user)
    output_root = Path(request.app.state.settings.report_root) / "xai"
    report = await XAIService.generate_for_prediction(
        session,
        prediction_id=prediction_id,
        output_root=output_root,
        background_size=payload.background_size,
        regenerate=payload.regenerate,
    )
    await AuditService.record(
        session,
        action="xai.generate",
        user_id=current_user.id,
        resource_type="xai_report",
        resource_id=str(report.id),
        details={"prediction_id": str(prediction_id), "status": report.status.value},
        request=request,
    )
    return _xai_response(report)


@router.get("/reports/{report_id}", response_model=XAIReportResponse)
async def get_xai_report(
    report_id: uuid.UUID,
    current_user: User = Depends(require_permissions(Permission.VIEW_EXPLANATIONS)),
    session: AsyncSession = Depends(get_db_session),
) -> XAIReportResponse:
    """Read an XAI report with hospital scoping through its prediction."""

    report = await XAIService.get_by_id(session, report_id)
    if report is None:
        raise NotFoundError("XAI report")
    await _assert_prediction_scope(
        session,
        prediction_id=report.prediction_id,
        current_user=current_user,
    )
    return _xai_response(report)


@router.get("/predictions/{prediction_id}", response_model=XAIReportResponse)
async def get_xai_report_by_prediction(
    prediction_id: uuid.UUID,
    current_user: User = Depends(require_permissions(Permission.VIEW_EXPLANATIONS)),
    session: AsyncSession = Depends(get_db_session),
) -> XAIReportResponse:
    """Read the XAI report associated with a prediction."""

    await _assert_prediction_scope(session, prediction_id=prediction_id, current_user=current_user)
    report = await XAIService.get_by_prediction_id(session, prediction_id)
    if report is None:
        raise NotFoundError("XAI report")
    return _xai_response(report)
