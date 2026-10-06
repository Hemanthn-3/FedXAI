"""Clinical prediction engine backed by versioned PyTorch model artifacts."""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from backend.app.core.errors import AppError
from backend.app.models.enums import DatasetType, ModelSource, RiskLevel
from backend.app.services.model_service import LoadedModelArtifact, ModelService
from fl_server.server.model import create_model

_log = logging.getLogger(__name__)

FEATURE_ALIASES: dict[str, tuple[str, ...]] = {
    "age": ("age",),
    "bp": ("bp", "blood_pressure", "bloodpressure", "trestbps"),
    "trestbps": ("trestbps", "bp", "blood_pressure", "bloodpressure"),
    "bloodpressure": ("bloodpressure", "bp", "blood_pressure"),
    "cholesterol": ("cholesterol", "chol"),
    "chol": ("chol", "cholesterol"),
    "glucose": ("glucose",),
    "pregnancies": ("pregnancies",),
    "insulin": ("insulin",),
    "bmi": ("bmi",),
    "sex": ("sex",),
    "cp": ("cp",),
    "fbs": ("fbs",),
    "thalach": ("thalach", "heart_rate", "heartrate"),
    "exang": ("exang",),
    "oldpeak": ("oldpeak",),
    "radius": ("radius",),
    "texture": ("texture",),
    "perimeter": ("perimeter",),
    "area": ("area",),
    "smoothness": ("smoothness",),
}


@dataclass(frozen=True)
class PredictionEngineResult:
    prediction: int
    probability: float
    risk_level: RiskLevel
    risk: str
    model_version: str
    dataset_type: DatasetType
    model_source: ModelSource
    feature_names: list[str]
    normalized_features: dict[str, float]
    warnings: list[str]


def risk_from_probability(probability: float) -> RiskLevel:
    if probability >= 0.65:
        return RiskLevel.HIGH
    if probability >= 0.35:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def risk_label(risk_level: RiskLevel) -> str:
    return risk_level.value.replace("_", " ").title()


class PredictionEngine:
    """Load a model artifact, validate clinical features, and run inference."""

    @staticmethod
    def _coerce_feature_value(name: str, value: Any) -> float:
        if isinstance(value, bool):
            return float(int(value))
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise AppError(
                f"Feature '{name}' must be numeric",
                status_code=422,
                code="invalid_feature_value",
                details={"feature": name},
            ) from exc
        if not np.isfinite(number):
            raise AppError(
                f"Feature '{name}' must be finite",
                status_code=422,
                code="invalid_feature_value",
                details={"feature": name},
            )
        return number

    @classmethod
    def _feature_vector(
        cls,
        features: dict[str, Any],
        feature_names: tuple[str, ...],
    ) -> tuple[np.ndarray, dict[str, float]]:
        normalized_input = {key.strip().lower(): value for key, value in features.items()}
        _log.debug("[PredictionEngine] received features: %s", normalized_input)
        _log.debug("[PredictionEngine] model expects features (in order): %s", feature_names)

        ordered_values: list[float] = []
        normalized_features: dict[str, float] = {}
        missing: list[str] = []
        for feature_name in feature_names:
            aliases = FEATURE_ALIASES.get(feature_name, (feature_name,))
            matched_alias = next(
                (alias for alias in aliases if alias in normalized_input),
                None,
            )
            if matched_alias is None:
                missing.append(feature_name)
                continue
            if matched_alias != feature_name:
                _log.warning(
                    "[PredictionEngine] feature '%s' resolved via alias '%s' — "
                    "use the canonical name for clarity",
                    feature_name, matched_alias,
                )
            value = cls._coerce_feature_value(feature_name, normalized_input[matched_alias])
            ordered_values.append(value)
            normalized_features[feature_name] = value
        if missing:
            raise AppError(
                "Prediction request is missing model-required features",
                status_code=422,
                code="missing_prediction_features",
                details={"missing_features": missing},
            )
        vector = np.asarray(ordered_values, dtype=np.float32)
        # Validate no NaN or Inf values before returning
        if not np.all(np.isfinite(vector)):
            bad = [
                feature_names[i]
                for i, v in enumerate(vector)
                if not np.isfinite(v)
            ]
            raise AppError(
                "Feature vector contains NaN or Inf values",
                status_code=422,
                code="invalid_feature_value",
                details={"invalid_features": bad},
            )
        _log.debug(
            "[PredictionEngine] ordered feature vector (pre-scaling): %s",
            dict(zip(feature_names, ordered_values, strict=False)),
        )
        return vector, normalized_features

    @staticmethod
    def _apply_preprocessing(vector: np.ndarray, metadata: dict[str, Any]) -> np.ndarray:
        transform_type = str(metadata.get("type", "identity")).lower()
        if transform_type == "identity":
            return vector
        if transform_type in {"standard", "standardization", "standard_scaler"}:
            means = np.asarray(metadata.get("means"), dtype=np.float32)
            scales = np.asarray(metadata.get("scales"), dtype=np.float32)
            if means.shape != vector.shape or scales.shape != vector.shape:
                raise AppError(
                    "Model preprocessing metadata shape does not match input features",
                    status_code=500,
                    code="invalid_model_preprocessing",
                )
            scales = np.where(scales == 0, 1.0, scales)
            return ((vector - means) / scales).astype(np.float32)
        raise AppError(
            f"Unsupported model preprocessing type: {transform_type}",
            status_code=500,
            code="unsupported_model_preprocessing",
        )

    @classmethod
    def predict(
        cls,
        *,
        artifact: LoadedModelArtifact,
        features: dict[str, Any],
        model_source: ModelSource,
    ) -> PredictionEngineResult:
        vector, normalized_features = cls._feature_vector(features, artifact.feature_names)
        # Validate feature count matches model input dimension
        if len(vector) != artifact.input_dim:
            raise AppError(
                f"Feature vector length {len(vector)} does not match "
                f"model input_dim {artifact.input_dim}",
                status_code=422,
                code="feature_dim_mismatch",
            )
        processed = cls._apply_preprocessing(vector, artifact.preprocessing)
        _log.debug(
            "[PredictionEngine] post-scaling feature vector: %s",
            dict(zip(artifact.feature_names, processed.tolist(), strict=False)),
        )
        model = create_model(artifact.input_dim)
        model.load_state_dict(artifact.state_dict, strict=True)
        model.eval()
        with torch.no_grad():
            tensor = torch.as_tensor(processed.reshape(1, -1), dtype=torch.float32)
            logit = model(tensor)
            probability = float(torch.sigmoid(logit).squeeze().cpu().item())
        predicted_class = int(probability >= 0.5)
        risk_level = risk_from_probability(probability)
        # Convention: single sigmoid output → P(class=1) = P(heart disease positive)
        _log.debug(
            "[PredictionEngine] raw logit=%.4f | sigmoid_prob=%.4f | "
            "predicted_class=%d (0=negative,1=positive) | risk=%s",
            float(logit.squeeze().cpu().item()),
            probability,
            predicted_class,
            risk_level.value,
        )
        return PredictionEngineResult(
            prediction=predicted_class,
            probability=round(probability, 6),
            risk_level=risk_level,
            risk=risk_label(risk_level),
            model_version=artifact.version,
            dataset_type=artifact.dataset_type,
            model_source=model_source,
            feature_names=list(artifact.feature_names),
            normalized_features=normalized_features,
            warnings=list(artifact.warnings),
        )

    @classmethod
    def predict_from_artifact(
        cls,
        *,
        path: str,
        features: dict[str, Any],
        dataset_type: DatasetType,
        model_source: ModelSource = ModelSource.FEDERATED,
        expected_sha256: str | None = None,
    ) -> PredictionEngineResult:
        artifact = ModelService.load_artifact(
            path=path,
            dataset_type=dataset_type,
            expected_sha256=expected_sha256,
        )
        return cls.predict(artifact=artifact, features=features, model_source=model_source)
