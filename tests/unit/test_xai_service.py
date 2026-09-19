import uuid

from backend.app.models.enums import XAIStatus
from backend.app.models.xai_report import XAIReport
from backend.app.services.xai_service import XAIService


def test_xai_service_extracts_top_features() -> None:
    report = XAIReport(
        prediction_id=uuid.uuid4(),
        status=XAIStatus.COMPLETED,
        feature_ranking=[
            {"feature": "glucose", "abs_contribution": 0.5},
            {"feature": "age", "abs_contribution": 0.2},
        ],
        local_contributions=[
            {"feature": "bp", "abs_contribution": 0.4},
            {"feature": "cholesterol", "abs_contribution": 0.3},
        ],
    )

    shap_features, lime_features = XAIService.top_features(report)

    assert shap_features == ["glucose", "age"]
    assert lime_features == ["bp", "cholesterol"]
