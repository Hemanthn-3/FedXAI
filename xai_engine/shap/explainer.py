"""SHAP explanation generation for FedPedia-XAI predictions."""

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import shap

from backend.app.services.model_service import LoadedModelArtifact
from xai_engine.common import (
    ArtifactPredictor,
    ensure_directory,
    prepare_explanation_context,
    ranked_contributions,
    write_json,
)


@dataclass(frozen=True)
class SHAPExplanationResult:
    shap_dir: Path
    summary_plot_path: Path
    waterfall_plot_path: Path
    bar_plot_path: Path
    force_plot_path: Path
    feature_ranking_path: Path
    feature_ranking: list[dict[str, float | str]]
    expected_value: float


class SHAPExplanationEngine:
    """Generate global and prediction-level SHAP artifacts."""

    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)

    @staticmethod
    def _positive_shap_values(values: Any) -> np.ndarray:
        array = np.asarray(values)
        if array.ndim == 3 and array.shape[-1] == 2:
            array = array[:, :, 1]
        if array.ndim == 2:
            return array.astype(np.float32)
        if array.ndim == 1:
            return array.reshape(1, -1).astype(np.float32)
        raise ValueError(f"Unsupported SHAP values shape: {array.shape}")

    @staticmethod
    def _positive_expected_value(value: Any) -> float:
        array = np.asarray(value)
        if array.ndim == 0:
            return float(array)
        if array.size >= 2:
            return float(array.reshape(-1)[-1])
        return float(array.reshape(-1)[0])

    def explain(
        self,
        *,
        prediction_id: str,
        artifact: LoadedModelArtifact,
        features: dict[str, Any],
        background_size: int = 48,
    ) -> SHAPExplanationResult:
        """Create SHAP summary, waterfall, bar, force, and ranking artifacts."""

        context = prepare_explanation_context(
            artifact=artifact,
            features=features,
            background_size=background_size,
        )
        predictor = ArtifactPredictor(artifact)
        output_dir = ensure_directory(self.output_root / str(prediction_id) / "shap")
        explainer = shap.KernelExplainer(predictor.predict_positive, context.background_raw)
        evaluation_rows = np.vstack(
            [context.raw_vector.reshape(1, -1), context.background_raw[:12]]
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            shap_values = explainer.shap_values(
                evaluation_rows,
                nsamples=max(64, artifact.input_dim * 16),
            )
        values = self._positive_shap_values(shap_values)
        expected_value = self._positive_expected_value(explainer.expected_value)
        instance_values = values[0]
        ranking = ranked_contributions(
            feature_names=artifact.feature_names,
            values=context.raw_vector,
            contributions=instance_values,
        )

        summary_plot_path = output_dir / "summary_plot.png"
        plt.figure(figsize=(10, 6))
        shap.summary_plot(
            values,
            evaluation_rows,
            feature_names=list(artifact.feature_names),
            show=False,
            plot_size=None,
        )
        plt.tight_layout()
        plt.savefig(summary_plot_path, dpi=160, bbox_inches="tight")
        plt.close()

        bar_plot_path = output_dir / "bar_plot.png"
        plt.figure(figsize=(9, 5))
        shap.summary_plot(
            values,
            evaluation_rows,
            feature_names=list(artifact.feature_names),
            plot_type="bar",
            show=False,
            plot_size=None,
        )
        plt.tight_layout()
        plt.savefig(bar_plot_path, dpi=160, bbox_inches="tight")
        plt.close()

        waterfall_plot_path = output_dir / "waterfall_plot.png"
        explanation = shap.Explanation(
            values=instance_values,
            base_values=expected_value,
            data=context.raw_vector,
            feature_names=list(artifact.feature_names),
        )
        plt.figure(figsize=(10, 6))
        shap.plots.waterfall(explanation, show=False, max_display=len(artifact.feature_names))
        plt.tight_layout()
        plt.savefig(waterfall_plot_path, dpi=160, bbox_inches="tight")
        plt.close()

        force_plot_path = output_dir / "force_plot.html"
        force_plot = shap.force_plot(
            expected_value,
            instance_values,
            context.raw_vector,
            feature_names=list(artifact.feature_names),
            matplotlib=False,
        )
        shap.save_html(str(force_plot_path), force_plot)

        feature_ranking_path = write_json(output_dir / "feature_ranking.json", ranking)
        write_json(
            output_dir / "manifest.json",
            {
                # Filenames only — manifests must stay valid when the artifacts
                # directory is mounted at a different path (e.g. across containers).
                "summary_plot": summary_plot_path.name,
                "waterfall_plot": waterfall_plot_path.name,
                "bar_plot": bar_plot_path.name,
                "force_plot": force_plot_path.name,
                "feature_ranking": feature_ranking_path.name,
                "expected_value": expected_value,
            },
        )

        return SHAPExplanationResult(
            shap_dir=output_dir,
            summary_plot_path=summary_plot_path,
            waterfall_plot_path=waterfall_plot_path,
            bar_plot_path=bar_plot_path,
            force_plot_path=force_plot_path,
            feature_ranking_path=feature_ranking_path,
            feature_ranking=ranking,
            expected_value=expected_value,
        )
