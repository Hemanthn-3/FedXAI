"""Report download API — PDF and CSV export for predictions and fairness analysis."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_permissions
from backend.app.auth.rbac import Permission
from backend.app.core.errors import NotFoundError
from backend.app.database import get_db_session
from backend.app.models.user import User
from backend.app.services.model_service import ModelService
from backend.app.services.patient_service import PatientService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.report_service import (
    CSVReportBuilder,
    FairnessCSVBuilder,
    PDFReportBuilder,
)
from backend.app.services.xai_service import XAIService

router = APIRouter()


# ---------------------------------------------------------------------------
# PDF report for a single prediction
# ---------------------------------------------------------------------------


@router.get(
    "/predictions/{prediction_id}/pdf",
    response_class=Response,
    summary="Download PDF clinical report",
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "text/html": {},
            },
            "description": "Clinical PDF report (or HTML fallback if reportlab is unavailable)",
        }
    },
)
async def download_prediction_pdf(
    prediction_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permissions(Permission.DOWNLOAD_REPORTS)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Generate and stream a PDF clinical report for a prediction."""
    prediction = await PredictionService.get_by_id(session, prediction_id)
    if prediction is None:
        raise NotFoundError("Prediction")

    patient = await PatientService.get_by_id(session, prediction.patient_id)
    if patient is None:
        raise NotFoundError("Patient")

    # XAI report (optional — report is generated without XAI if absent)
    xai_report = await XAIService.get_by_prediction_id(session, prediction_id)
    shap_features: list[str] = []
    lime_features: list[str] = []
    feature_ranking: list[dict] = []
    local_contributions: list[dict] = []
    shap_plot: str | None = None
    lime_plot: str | None = None

    if xai_report is not None:
        shap_features, lime_features = XAIService.top_features(xai_report)
        feature_ranking = list(xai_report.feature_ranking or [])
        local_contributions = list(xai_report.local_contributions or [])
        if xai_report.shap_path:
            bar = Path(xai_report.shap_path) / "bar_plot.png"
            if bar.exists():
                shap_plot = str(bar)
        if xai_report.lime_path:
            local = Path(xai_report.lime_path) / "local_explanation.png"
            if local.exists():
                lime_plot = str(local)

    # Model version
    model_version = "N/A"
    if prediction.global_model_id is not None:
        gm = await ModelService.get_by_id(session, prediction.global_model_id)
        if gm is not None:
            model_version = str(gm.version)

    report_root = Path(request.app.state.settings.report_root) / "pdf"
    output_path = report_root / f"{prediction_id}.pdf"

    builder = PDFReportBuilder(
        prediction_id=prediction_id,
        patient_id=prediction.patient_id,
        dataset_type=prediction.dataset_type,
        model_source=prediction.model_source.value,
        prediction=prediction.prediction,
        risk_level=prediction.risk_level.value,
        probability=prediction.probability,
        doctor_notes=prediction.doctor_notes,
        feature_ranking=feature_ranking,
        local_contributions=local_contributions,
        top_shap_features=shap_features,
        top_lime_features=lime_features,
        model_version=model_version,
        shap_plot_path=shap_plot,
        lime_plot_path=lime_plot,
    )

    saved_path = builder.save_pdf(output_path)

    content = saved_path.read_bytes()
    media_type = "application/pdf" if saved_path.suffix == ".pdf" else "text/html"
    filename = saved_path.name
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# CSV report for multiple predictions
# ---------------------------------------------------------------------------


@router.get(
    "/predictions/csv",
    response_class=Response,
    summary="Download CSV of recent predictions",
    responses={200: {"content": {"text/csv": {}}, "description": "CSV predictions export"}},
)
async def download_predictions_csv(
    limit: int = Query(500, ge=1, le=5000),
    current_user: User = Depends(require_permissions(Permission.DOWNLOAD_REPORTS)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Export the most recent predictions (and their XAI status) as CSV."""
    predictions = await PredictionService.list_predictions(
        session,
        hospital_id=None,
        limit=limit,
    )

    builder = CSVReportBuilder()
    for pred in predictions:
        xai = await XAIService.get_by_prediction_id(session, pred.id)
        shap_f: list[str] = []
        lime_f: list[str] = []
        xai_status = None
        if xai:
            shap_f, lime_f = XAIService.top_features(xai)
            xai_status = xai.status.value

        builder.add_prediction_row(
            prediction_id=pred.id,
            patient_id=pred.patient_id,
            dataset_type=pred.dataset_type.value,
            model_source=pred.model_source.value,
            prediction=pred.prediction,
            risk_level=pred.risk_level.value,
            probability=pred.probability,
            doctor_notes=pred.doctor_notes,
            shap_top_features=shap_f,
            lime_top_features=lime_f,
            xai_status=xai_status,
            created_at=pred.created_at,
        )

    csv_bytes = builder.build_bytes()
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="predictions_export.csv"'},
    )


# ---------------------------------------------------------------------------
# Fairness report CSV
# ---------------------------------------------------------------------------


@router.post(
    "/fairness/csv",
    response_class=Response,
    summary="Download fairness analysis as CSV",
    responses={200: {"content": {"text/csv": {}}, "description": "Fairness CSV export"}},
)
async def download_fairness_csv(
    payload: dict,
    current_user: User = Depends(  # noqa: ARG001
        require_permissions(Permission.ANALYZE_FAIRNESS)
    ),
) -> Response:
    """Export a fairness analysis report (as returned by POST /analytics/fairness) to CSV."""
    csv_bytes = FairnessCSVBuilder(payload).build_bytes()
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fairness_report.csv"'},
    )
