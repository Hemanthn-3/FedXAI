"""SHAP and LIME report persistence service."""

import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AppError, NotFoundError
from backend.app.models.enums import XAIStatus
from backend.app.models.global_model import GlobalModel
from backend.app.models.prediction import Prediction
from backend.app.models.xai_report import XAIReport
from backend.app.services.model_service import ModelService
from backend.app.services.prediction_service import PredictionService
from xai_engine.lime import LIMEExplanationEngine
from xai_engine.shap import SHAPExplanationEngine


class XAIService:
    """Generate and persist SHAP/LIME artifacts for a prediction."""

    @staticmethod
    async def get_by_id(session: AsyncSession, report_id: uuid.UUID) -> XAIReport | None:
        return await session.get(XAIReport, report_id)

    @staticmethod
    async def get_by_prediction_id(
        session: AsyncSession,
        prediction_id: uuid.UUID,
    ) -> XAIReport | None:
        result = await session.execute(
            select(XAIReport).where(XAIReport.prediction_id == prediction_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _prediction_and_model(
        session: AsyncSession,
        prediction_id: uuid.UUID,
    ) -> tuple[Prediction, GlobalModel]:
        prediction = await PredictionService.get_by_id(session, prediction_id)
        if prediction is None:
            raise NotFoundError("Prediction")
        if prediction.global_model_id is None:
            raise AppError(
                "Prediction is not linked to a global model artifact",
                status_code=409,
                code="prediction_missing_model",
            )
        model = await ModelService.get_by_id(session, prediction.global_model_id)
        if model is None:
            raise NotFoundError("Global model")
        return prediction, model

    @staticmethod
    def _clean_existing_artifacts(report: XAIReport) -> None:
        for path_value in (report.shap_path, report.lime_path):
            if path_value:
                path = Path(path_value)
                if path.exists() and path.is_dir():
                    shutil.rmtree(path)

    @classmethod
    async def generate_for_prediction(
        cls,
        session: AsyncSession,
        *,
        prediction_id: uuid.UUID,
        output_root: str | Path,
        background_size: int = 48,
        regenerate: bool = False,
    ) -> XAIReport:
        prediction, model = await cls._prediction_and_model(session, prediction_id)
        existing = await cls.get_by_prediction_id(session, prediction_id)
        if existing is not None and existing.status == XAIStatus.COMPLETED and not regenerate:
            return existing

        report = existing or XAIReport(prediction_id=prediction_id)
        if existing is None:
            session.add(report)
            await session.flush()
        else:
            cls._clean_existing_artifacts(existing)

        try:
            artifact = ModelService.load_artifact(
                path=model.path,
                dataset_type=model.dataset_type,
                expected_sha256=None,  # already verified at registration
            )
            shap_result = SHAPExplanationEngine(output_root).explain(
                prediction_id=str(prediction_id),
                artifact=artifact,
                features=prediction.input_features,
                background_size=background_size,
            )
            lime_result = LIMEExplanationEngine(output_root).explain(
                prediction_id=str(prediction_id),
                artifact=artifact,
                features=prediction.input_features,
                background_size=background_size,
            )
            report.shap_path = str(shap_result.shap_dir)
            report.lime_path = str(lime_result.lime_dir)
            report.feature_ranking = shap_result.feature_ranking
            report.local_contributions = lime_result.local_contributions
            report.status = XAIStatus.COMPLETED
            report.error_message = None
        except Exception as exc:
            report.status = XAIStatus.FAILED
            report.error_message = str(exc)[:4000]
            await session.flush()
            raise

        await session.flush()
        await session.refresh(report)
        return report

    @staticmethod
    def top_features(report: XAIReport) -> tuple[list[str], list[str]]:
        """Return top feature names from SHAP (by abs importance) and LIME.

        The full signed contribution data is available in report.feature_ranking
        and report.local_contributions respectively — the frontend uses those
        directly for the detailed table.  This helper returns just the compact
        name lists used for the summary panels.
        """
        shap_features = [
            str(item.get("feature"))
            for item in (report.feature_ranking or [])[:5]
            if item.get("feature")
        ]
        lime_features = [
            str(item.get("feature"))
            for item in (report.local_contributions or [])[:5]
            if item.get("feature")
        ]
        return shap_features, lime_features
