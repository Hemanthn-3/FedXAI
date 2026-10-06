"""Shared utilities for SHAP and LIME explainability engines."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from backend.app.core.errors import AppError
from backend.app.services.model_service import LoadedModelArtifact
from backend.app.services.prediction_engine import PredictionEngine
from fl_server.server.model import create_model


@dataclass(frozen=True)
class ExplanationContext:
    """Prepared model, feature vector, and reference data for XAI engines."""

    artifact: LoadedModelArtifact
    raw_vector: np.ndarray
    processed_vector: np.ndarray
    normalized_features: dict[str, float]
    background_raw: np.ndarray


def ensure_directory(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def prepare_explanation_context(
    *,
    artifact: LoadedModelArtifact,
    features: dict[str, Any],
    background_size: int = 48,
) -> ExplanationContext:
    """Validate features and build a privacy-safe synthetic reference matrix.

    Raw hospital training rows are not centralized. The reference matrix is
    deterministic and derived from artifact preprocessing metadata plus the
    current prediction, making XAI generation possible without moving patient
    datasets to the server.
    """

    raw_vector, normalized_features = PredictionEngine._feature_vector(  # noqa: SLF001
        features,
        artifact.feature_names,
    )
    processed_vector = PredictionEngine._apply_preprocessing(  # noqa: SLF001
        raw_vector,
        artifact.preprocessing,
    )
    background_raw = generate_reference_background(
        raw_vector=raw_vector,
        artifact=artifact,
        size=background_size,
    )
    return ExplanationContext(
        artifact=artifact,
        raw_vector=raw_vector,
        processed_vector=processed_vector,
        normalized_features=normalized_features,
        background_raw=background_raw,
    )


def generate_reference_background(
    *,
    raw_vector: np.ndarray,
    artifact: LoadedModelArtifact,
    size: int = 48,
) -> np.ndarray:
    """Create a deterministic local reference dataset for explainability."""

    if size < 8:
        raise ValueError("background size must be at least 8")
    preprocessing = artifact.preprocessing
    transform_type = str(preprocessing.get("type", "identity")).lower()
    if transform_type in {"standard", "standardization", "standard_scaler"}:
        means = np.asarray(preprocessing.get("means"), dtype=np.float32)
        scales = np.asarray(preprocessing.get("scales"), dtype=np.float32)
        if means.shape == raw_vector.shape and scales.shape == raw_vector.shape:
            center = means
            spread = np.where(scales == 0, 1.0, scales)
        else:
            center = raw_vector
            spread = np.maximum(np.abs(raw_vector) * 0.05, 1.0)
    elif transform_type == "identity":
        center = raw_vector
        spread = np.maximum(np.abs(raw_vector) * 0.05, 1.0)
    else:
        raise AppError(
            f"Unsupported model preprocessing type: {transform_type}",
            status_code=500,
            code="unsupported_model_preprocessing",
        )

    offsets = np.linspace(-1.0, 1.0, num=size, dtype=np.float32).reshape(-1, 1)
    feature_scales = np.linspace(0.25, 1.0, num=raw_vector.shape[0], dtype=np.float32)
    background = center.reshape(1, -1) + offsets * spread.reshape(1, -1) * feature_scales
    background[0] = raw_vector
    return background.astype(np.float32)


class ArtifactPredictor:
    """Callable raw-feature probability predictor for SHAP and LIME."""

    def __init__(self, artifact: LoadedModelArtifact) -> None:
        self.artifact = artifact
        self.model = create_model(artifact.input_dim)
        self.model.load_state_dict(artifact.state_dict, strict=True)
        self.model.eval()

    def predict_positive(self, raw_rows: np.ndarray) -> np.ndarray:
        rows = np.asarray(raw_rows, dtype=np.float32)
        if rows.ndim == 1:
            rows = rows.reshape(1, -1)
        processed_rows = np.vstack(
            [
                PredictionEngine._apply_preprocessing(row, self.artifact.preprocessing)  # noqa: SLF001
                for row in rows
            ]
        ).astype(np.float32)
        with torch.no_grad():
            logits = self.model(torch.as_tensor(processed_rows, dtype=torch.float32))
            probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        return probabilities.reshape(-1)

    def predict_proba(self, raw_rows: np.ndarray) -> np.ndarray:
        positive = self.predict_positive(raw_rows)
        return np.column_stack([1.0 - positive, positive]).astype(np.float32)


def ranked_contributions(
    *,
    feature_names: tuple[str, ...],
    values: np.ndarray,
    contributions: np.ndarray,
) -> list[dict[str, float | str]]:
    """Return absolute-importance sorted feature contributions."""

    ranking = []
    for name, value, contribution in zip(feature_names, values, contributions, strict=True):
        ranking.append(
            {
                "feature": name,
                "value": float(value),
                "contribution": float(contribution),
                "abs_contribution": float(abs(contribution)),
            }
        )
    return sorted(ranking, key=lambda item: float(item["abs_contribution"]), reverse=True)