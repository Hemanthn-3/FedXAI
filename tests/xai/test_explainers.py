import torch

from backend.app.models.enums import DatasetType
from backend.app.services.model_service import ModelService
from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.registry import ModelRegistry
from xai_engine.lime import LIMEExplanationEngine
from xai_engine.shap import SHAPExplanationEngine


def _artifact(tmp_path):
    model = create_model(input_dim=4)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.network[-1].bias.fill_(1.5)
    registry = ModelRegistry(tmp_path / "models")
    saved = registry.save_global_model(
        parameters=get_model_parameters(model),
        input_dim=4,
        dataset_type=DatasetType.HEART_DISEASE,
        round_number=1,
        metrics={"accuracy": 1.0},
        feature_names=("age", "bp", "cholesterol", "glucose"),
    )
    return ModelService.load_artifact(
        path=saved.path,
        dataset_type=DatasetType.HEART_DISEASE,
        expected_sha256=saved.checksum_sha256,
    )


def test_shap_engine_generates_required_plots_and_feature_ranking(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    result = SHAPExplanationEngine(tmp_path / "reports").explain(
        prediction_id="prediction-1",
        artifact=artifact,
        features={"age": 52, "bp": 130, "cholesterol": 240, "glucose": 115},
        background_size=8,
    )

    assert result.summary_plot_path.exists()
    assert result.waterfall_plot_path.exists()
    assert result.bar_plot_path.exists()
    assert result.force_plot_path.exists()
    assert result.feature_ranking_path.exists()
    assert [item["feature"] for item in result.feature_ranking] == [
        "age",
        "bp",
        "cholesterol",
        "glucose",
    ]


def test_lime_engine_generates_local_explanation_and_contributions(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    result = LIMEExplanationEngine(tmp_path / "reports").explain(
        prediction_id="prediction-1",
        artifact=artifact,
        features={"age": 52, "bp": 130, "cholesterol": 240, "glucose": 115},
        background_size=16,
    )

    assert result.local_plot_path.exists()
    assert result.html_path.exists()
    assert result.contributions_path.exists()
    assert result.local_contributions
    assert result.top_features
