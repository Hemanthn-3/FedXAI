"""LIME local explanation generation for FedPedia-XAI predictions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from lime.lime_tabular import LimeTabularExplainer

from backend.app.services.model_service import LoadedModelArtifact
from xai_engine.common import (
    ArtifactPredictor,
    ensure_directory,
    prepare_explanation_context,
    write_json,
)


@dataclass(frozen=True)
class LIMEExplanationResult:
    lime_dir: Path
    local_plot_path: Path
    html_path: Path
    contributions_path: Path
    local_contributions: list[dict[str, float | str]]
    top_features: list[str]


class LIMEExplanationEngine:
    """Generate local LIME explanations and contribution artifacts."""

    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)

    @staticmethod
    def _parse_contribution(
        label: str,
        contribution: float,
        feature_names: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, float | str]:
        # LIME labels can be double-bounded ("2.70 < oldpeak <= 3.29"), single-bounded ("oldpeak > 130"), or plain names.
        tokens = (
            label.replace("<=", " ")
            .replace(">=", " ")
            .replace("<", " ")
            .replace(">", " ")
            .replace("=", " ")
            .split()
        )
        matched_feature = None
        if feature_names:
            feature_map = {f.lower(): f for f in feature_names}
            for token in tokens:
                if token.lower() in feature_map:
                    matched_feature = feature_map[token.lower()]
                    break
        if matched_feature is None:
            for token in tokens:
                try:
                    float(token)
                except ValueError:
                    matched_feature = token
                    break
        feature = matched_feature or (tokens[0] if tokens else label)
        return {
            "feature": feature,
            "description": label,
            "contribution": float(contribution),
            "abs_contribution": float(abs(contribution)),
        }

    def explain(
        self,
        *,
        prediction_id: str,
        artifact: LoadedModelArtifact,
        features: dict[str, Any],
        background_size: int = 48,
        num_features: int | None = None,
    ) -> LIMEExplanationResult:
        """Create local LIME plot, HTML explanation, and contribution JSON."""

        context = prepare_explanation_context(
            artifact=artifact,
            features=features,
            background_size=background_size,
        )
        predictor = ArtifactPredictor(artifact)
        output_dir = ensure_directory(self.output_root / str(prediction_id) / "lime")
        explainer = LimeTabularExplainer(
            training_data=context.background_raw,
            feature_names=list(artifact.feature_names),
            class_names=["negative", "positive"],
            mode="classification",
            discretize_continuous=True,
            random_state=42,
        )
        explanation = explainer.explain_instance(
            data_row=context.raw_vector,
            predict_fn=predictor.predict_proba,
            num_features=num_features or len(artifact.feature_names),
            labels=(1,),
        )
        contributions = [
            self._parse_contribution(label, contribution, feature_names=artifact.feature_names)
            for label, contribution in explanation.as_list(label=1)
        ]
        contributions = sorted(
            contributions,
            key=lambda item: float(item["abs_contribution"]),
            reverse=True,
        )
        top_features = [str(item["feature"]) for item in contributions]

        local_plot_path = output_dir / "local_explanation.png"
        figure = explanation.as_pyplot_figure(label=1)
        figure.set_size_inches(9, 5)
        plt.tight_layout()
        figure.savefig(local_plot_path, dpi=160, bbox_inches="tight")
        plt.close(figure)

        html_path = output_dir / "local_explanation.html"
        html_path.write_text(explanation.as_html(labels=(1,)), encoding="utf-8")

        contributions_path = write_json(output_dir / "feature_contributions.json", contributions)
        write_json(
            output_dir / "manifest.json",
            {
                "local_explanation": str(local_plot_path),
                "html": str(html_path),
                "feature_contributions": str(contributions_path),
                "top_features": top_features,
            },
        )

        return LIMEExplanationResult(
            lime_dir=output_dir,
            local_plot_path=local_plot_path,
            html_path=html_path,
            contributions_path=contributions_path,
            local_contributions=contributions,
            top_features=top_features,
        )
