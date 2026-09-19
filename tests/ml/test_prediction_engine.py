import pytest
import torch

from backend.app.core.errors import AppError
from backend.app.models.enums import DatasetType, ModelSource, RiskLevel
from backend.app.services.model_service import ModelService
from backend.app.services.prediction_engine import PredictionEngine
from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.registry import ModelRegistry


def _compact_artifact(tmp_path, *, bias: float = 2.0):
    model = create_model(input_dim=4)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.network[-1].bias.fill_(bias)
    registry = ModelRegistry(tmp_path)
    artifact = registry.save_global_model(
        parameters=get_model_parameters(model),
        input_dim=4,
        dataset_type=DatasetType.HEART_DISEASE,
        round_number=1,
        metrics={"accuracy": 1.0},
        feature_names=("age", "bp", "cholesterol", "glucose"),
    )
    return artifact


def test_prediction_engine_returns_requested_output_shape(tmp_path) -> None:
    artifact = _compact_artifact(tmp_path)

    result = PredictionEngine.predict_from_artifact(
        path=str(artifact.path),
        expected_sha256=artifact.checksum_sha256,
        dataset_type=DatasetType.HEART_DISEASE,
        model_source=ModelSource.FEDERATED,
        features={"age": 52, "bp": 130, "cholesterol": 240, "glucose": 115},
    )

    assert result.prediction == 1
    assert result.risk_level == RiskLevel.HIGH
    assert result.risk == "High"
    assert result.probability > 0.65
    assert result.normalized_features == {
        "age": 52.0,
        "bp": 130.0,
        "cholesterol": 240.0,
        "glucose": 115.0,
    }


def test_prediction_engine_supports_feature_aliases(tmp_path) -> None:
    artifact = _compact_artifact(tmp_path)

    result = PredictionEngine.predict_from_artifact(
        path=str(artifact.path),
        expected_sha256=artifact.checksum_sha256,
        dataset_type=DatasetType.HEART_DISEASE,
        features={"age": 52, "blood_pressure": 130, "chol": 240, "glucose": 115},
    )

    assert result.normalized_features["bp"] == 130.0
    assert result.normalized_features["cholesterol"] == 240.0


def test_prediction_engine_rejects_missing_model_features(tmp_path) -> None:
    artifact = _compact_artifact(tmp_path)

    with pytest.raises(AppError) as exc_info:
        PredictionEngine.predict_from_artifact(
            path=str(artifact.path),
            expected_sha256=artifact.checksum_sha256,
            dataset_type=DatasetType.HEART_DISEASE,
            features={"age": 52, "bp": 130, "cholesterol": 240},
        )

    assert exc_info.value.code == "missing_prediction_features"
    assert exc_info.value.details["missing_features"] == ["glucose"]


def test_model_service_detects_checksum_mismatch(tmp_path) -> None:
    artifact = _compact_artifact(tmp_path)

    with pytest.raises(AppError) as exc_info:
        ModelService.load_artifact(
            path=artifact.path,
            expected_sha256="0" * 64,
            dataset_type=DatasetType.HEART_DISEASE,
        )

    assert exc_info.value.code == "model_checksum_mismatch"
