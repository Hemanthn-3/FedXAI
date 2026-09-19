"""Fairness analysis module — bias detection and group-level metric comparison."""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value: float | None, default: float = 0.0) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return float(value)


def _classification_metrics(
    labels: list[int], predictions: list[int]
) -> dict[str, float]:
    """Compute accuracy, PPV (precision), TPR (recall), FPR for a binary group."""
    if not labels:
        return {"count": 0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "fpr": 0.0}

    tp = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 1)
    tn = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 0 and p == 0)
    fp = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 0)

    accuracy = (tp + tn) / len(labels)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    return {
        "count": len(labels),
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "fpr": round(fpr, 6),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


# ---------------------------------------------------------------------------
# Bias detection
# ---------------------------------------------------------------------------

BIAS_THRESHOLD_DISPARATE_IMPACT = 0.80  # 80 % rule
BIAS_THRESHOLD_EQUALIZED_ODDS = 0.10    # ±10 pp tolerance


def disparate_impact(positive_rate_privileged: float, positive_rate_unprivileged: float) -> float:
    """Ratio of positive prediction rates between unprivileged and privileged groups.

    A value below 0.80 indicates potential disparate impact (adverse impact).
    """
    if positive_rate_privileged == 0.0:
        return 1.0
    return round(positive_rate_unprivileged / positive_rate_privileged, 6)


def equalized_odds_difference(
    *,
    tpr_privileged: float,
    tpr_unprivileged: float,
    fpr_privileged: float,
    fpr_unprivileged: float,
) -> dict[str, float]:
    """Absolute differences in TPR and FPR between groups."""
    return {
        "tpr_difference": round(abs(tpr_privileged - tpr_unprivileged), 6),
        "fpr_difference": round(abs(fpr_privileged - fpr_unprivileged), 6),
        "max_difference": round(
            max(abs(tpr_privileged - tpr_unprivileged), abs(fpr_privileged - fpr_unprivileged)),
            6,
        ),
    }


def statistical_parity_difference(
    positive_rate_privileged: float, positive_rate_unprivileged: float
) -> float:
    """Difference in positive prediction rates (SPD). Ideal = 0."""
    return round(positive_rate_unprivileged - positive_rate_privileged, 6)


# ---------------------------------------------------------------------------
# Group analysis
# ---------------------------------------------------------------------------

class GroupFairnessAnalysis:
    """Analyse fairness metrics across demographic groups defined by a feature split."""

    def __init__(
        self,
        *,
        feature_name: str,
        groups: dict[str, dict[str, Any]],
        privileged_group: str,
    ) -> None:
        """
        Parameters
        ----------
        feature_name:
            Name of the feature used to split groups (e.g. ``"sex"``).
        groups:
            Mapping of group label → dict with keys ``labels`` and ``predictions``
            (each a list of ints).
        privileged_group:
            Group label treated as the reference / privileged group.
        """
        self.feature_name = feature_name
        self.privileged_group = privileged_group
        self._metrics: dict[str, dict[str, float]] = {
            label: _classification_metrics(
                g["labels"], g["predictions"]
            )
            for label, g in groups.items()
        }
        self._positive_rates: dict[str, float] = {
            label: _safe(g.get("positive_rate"))
            for label, g in groups.items()
        }

    # ------------------------------------------------------------------
    # Bias metrics against each unprivileged group
    # ------------------------------------------------------------------

    def _privileged_metrics(self) -> dict[str, float]:
        return self._metrics.get(self.privileged_group, {})

    def _privileged_positive_rate(self) -> float:
        return self._positive_rates.get(self.privileged_group, 0.0)

    def group_metrics(self) -> dict[str, dict[str, float]]:
        return dict(self._metrics)

    def disparate_impact_table(self) -> dict[str, float]:
        pr_priv = self._privileged_positive_rate()
        return {
            label: disparate_impact(pr_priv, pr)
            for label, pr in self._positive_rates.items()
            if label != self.privileged_group
        }

    def statistical_parity_table(self) -> dict[str, float]:
        pr_priv = self._privileged_positive_rate()
        return {
            label: statistical_parity_difference(pr_priv, pr)
            for label, pr in self._positive_rates.items()
            if label != self.privileged_group
        }

    def equalized_odds_table(self) -> dict[str, dict[str, float]]:
        priv = self._privileged_metrics()
        results: dict[str, dict[str, float]] = {}
        for label, metrics in self._metrics.items():
            if label == self.privileged_group:
                continue
            results[label] = equalized_odds_difference(
                tpr_privileged=_safe(priv.get("recall")),
                tpr_unprivileged=_safe(metrics.get("recall")),
                fpr_privileged=_safe(priv.get("fpr")),
                fpr_unprivileged=_safe(metrics.get("fpr")),
            )
        return results

    # ------------------------------------------------------------------
    # Bias flags
    # ------------------------------------------------------------------

    def bias_flags(self) -> dict[str, list[str]]:
        flags: dict[str, list[str]] = {}
        di_table = self.disparate_impact_table()
        eo_table = self.equalized_odds_table()

        for label in di_table:
            group_flags: list[str] = []
            if di_table[label] < BIAS_THRESHOLD_DISPARATE_IMPACT:
                group_flags.append(
                    f"Disparate impact: {di_table[label]:.3f} < {BIAS_THRESHOLD_DISPARATE_IMPACT}"
                )
            if label in eo_table:
                max_eo = _safe(eo_table[label].get("max_difference"))
                if max_eo > BIAS_THRESHOLD_EQUALIZED_ODDS:
                    threshold = BIAS_THRESHOLD_EQUALIZED_ODDS
                    group_flags.append(
                        f"Equalized odds violation: Δ = {max_eo:.3f} > {threshold}"
                    )
            flags[label] = group_flags
        return flags

    def overall_bias_detected(self) -> bool:
        return any(flags for flags in self.bias_flags().values())

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def report(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "privileged_group": self.privileged_group,
            "group_metrics": self.group_metrics(),
            "disparate_impact": self.disparate_impact_table(),
            "statistical_parity": self.statistical_parity_table(),
            "equalized_odds": self.equalized_odds_table(),
            "bias_flags": self.bias_flags(),
            "bias_detected": self.overall_bias_detected(),
        }


# ---------------------------------------------------------------------------
# Feature influence comparison across groups
# ---------------------------------------------------------------------------

class FeatureInfluenceComparison:
    """Compare SHAP feature importance rankings across groups or learning modes."""

    def __init__(
        self,
        *,
        federated_ranking: list[dict[str, Any]],
        centralized_ranking: list[dict[str, Any]],
    ) -> None:
        """
        Parameters
        ----------
        federated_ranking / centralized_ranking:
            Ordered list of ``{feature, abs_contribution}`` dicts.
        """
        self._fl = self._to_map(federated_ranking)
        self._cl = self._to_map(centralized_ranking)

    @staticmethod
    def _to_map(ranking: list[dict[str, Any]]) -> dict[str, float]:
        return {
            str(item["feature"]): _safe(item.get("abs_contribution"))
            for item in ranking
            if "feature" in item
        }

    def rank_shift_table(self) -> list[dict[str, Any]]:
        """Return features sorted by absolute difference in importance between modes."""
        all_features = set(self._fl) | set(self._cl)
        rows: list[dict[str, Any]] = []
        fl_values = list(self._fl.values())
        cl_values = list(self._cl.values())

        for feature in all_features:
            fl_val = self._fl.get(feature, 0.0)
            cl_val = self._cl.get(feature, 0.0)
            fl_rank = (
                sorted(fl_values, reverse=True).index(fl_val) + 1
                if fl_val in fl_values
                else len(fl_values) + 1
            )
            cl_rank = (
                sorted(cl_values, reverse=True).index(cl_val) + 1
                if cl_val in cl_values
                else len(cl_values) + 1
            )
            rows.append(
                {
                    "feature": feature,
                    "fl_importance": round(fl_val, 6),
                    "centralized_importance": round(cl_val, 6),
                    "importance_delta": round(fl_val - cl_val, 6),
                    "fl_rank": fl_rank,
                    "centralized_rank": cl_rank,
                    "rank_shift": cl_rank - fl_rank,
                }
            )
        return sorted(rows, key=lambda r: abs(float(r["importance_delta"])), reverse=True)

    def top_consistent_features(self, n: int = 5) -> list[str]:
        """Features with smallest importance delta — most stable across modes."""
        table = self.rank_shift_table()
        stable = sorted(table, key=lambda r: abs(float(r["importance_delta"])))
        return [str(r["feature"]) for r in stable[:n]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank_shift_table": self.rank_shift_table(),
            "top_consistent_features": self.top_consistent_features(),
        }


# ---------------------------------------------------------------------------
# Full fairness report builder
# ---------------------------------------------------------------------------

class FairnessReportBuilder:
    """Compose a complete fairness report from group analyses and feature comparisons."""

    def __init__(self) -> None:
        self._group_analyses: list[GroupFairnessAnalysis] = []
        self._feature_comparison: FeatureInfluenceComparison | None = None

    def add_group_analysis(self, analysis: GroupFairnessAnalysis) -> FairnessReportBuilder:
        self._group_analyses.append(analysis)
        return self

    def set_feature_comparison(
        self, comparison: FeatureInfluenceComparison
    ) -> FairnessReportBuilder:
        self._feature_comparison = comparison
        return self

    def build(self) -> dict[str, Any]:
        any_bias = any(a.overall_bias_detected() for a in self._group_analyses)
        return {
            "overall_bias_detected": any_bias,
            "group_analyses": [a.report() for a in self._group_analyses],
            "feature_influence_comparison": (
                self._feature_comparison.to_dict() if self._feature_comparison else None
            ),
            "recommendation": (
                "Bias detected in one or more demographic groups. "
                "Review training data distribution and consider reweighting or resampling."
                if any_bias
                else "No significant bias detected across analysed groups."
            ),
        }
