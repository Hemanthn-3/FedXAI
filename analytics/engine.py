"""Analytics engine — aggregate FL metrics and produce comparison reports."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _safe(value: float | None, default: float = 0.0) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return float(value)


def _round_dict(d: dict[str, float | None]) -> dict[str, float]:
    return {k: round(_safe(v), 6) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Per-round summary
# ---------------------------------------------------------------------------

class RoundSummary:
    """One FL training round's aggregated view."""

    __slots__ = (
        "round_number",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "loss",
        "participating_clients",
        "total_clients",
        "node_ids",
        "aggregation_strategy",
        "status",
        "timestamp",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        self.round_number: int = int(row.get("round_number", 0))
        self.accuracy: float = _safe(row.get("accuracy"))
        self.precision: float = _safe(row.get("precision"))
        self.recall: float = _safe(row.get("recall"))
        self.f1: float = _safe(row.get("f1"))
        self.roc_auc: float = _safe(row.get("roc_auc"))
        self.loss: float = _safe(row.get("loss"))
        self.participating_clients: int = int(row.get("participating_clients", 0))
        self.total_clients: int = int(row.get("total_clients", 1))
        self.node_ids: list[str] = list(row.get("participating_nodes") or [])
        self.aggregation_strategy: str = str(row.get("aggregation_strategy", "fedavg"))
        self.status: str = str(row.get("status", "unknown"))
        self.timestamp: str = str(row.get("timestamp", ""))

    def participation_rate(self) -> float:
        if self.total_clients == 0:
            return 0.0
        return round(self.participating_clients / self.total_clients, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "loss": self.loss,
            "participating_clients": self.participating_clients,
            "total_clients": self.total_clients,
            "participation_rate": self.participation_rate(),
            "node_ids": self.node_ids,
            "aggregation_strategy": self.aggregation_strategy,
            "status": self.status,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# FL Analytics Engine
# ---------------------------------------------------------------------------

class FLAnalyticsEngine:
    """Compute FL training analytics from a sequence of round records."""

    def __init__(self, rounds: list[dict[str, Any]]) -> None:
        self.rounds: list[RoundSummary] = [RoundSummary(r) for r in rounds]

    # ------------------------------------------------------------------
    # Metric series
    # ------------------------------------------------------------------

    def accuracy_series(self) -> list[dict[str, Any]]:
        return [{"round": r.round_number, "accuracy": r.accuracy} for r in self.rounds]

    def loss_series(self) -> list[dict[str, Any]]:
        return [{"round": r.round_number, "loss": r.loss} for r in self.rounds]

    def f1_series(self) -> list[dict[str, Any]]:
        return [{"round": r.round_number, "f1": r.f1} for r in self.rounds]

    def roc_auc_series(self) -> list[dict[str, Any]]:
        return [{"round": r.round_number, "roc_auc": r.roc_auc} for r in self.rounds]

    def participation_series(self) -> list[dict[str, Any]]:
        return [
            {
                "round": r.round_number,
                "participating": r.participating_clients,
                "total": r.total_clients,
                "rate": r.participation_rate(),
            }
            for r in self.rounds
        ]

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------

    def _metric_stats(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {"min": 0.0, "max": 0.0, "mean": 0.0, "final": 0.0}
        return {
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "mean": round(sum(values) / len(values), 6),
            "final": round(values[-1], 6),
        }

    def summary_stats(self) -> dict[str, Any]:
        completed = [r for r in self.rounds if r.status == "completed"]
        if not completed:
            return {"total_rounds": len(self.rounds), "completed_rounds": 0}

        return {
            "total_rounds": len(self.rounds),
            "completed_rounds": len(completed),
            "accuracy": self._metric_stats([r.accuracy for r in completed]),
            "precision": self._metric_stats([r.precision for r in completed]),
            "recall": self._metric_stats([r.recall for r in completed]),
            "f1": self._metric_stats([r.f1 for r in completed]),
            "roc_auc": self._metric_stats([r.roc_auc for r in completed]),
            "loss": self._metric_stats([r.loss for r in completed]),
            "avg_participation_rate": round(
                sum(r.participation_rate() for r in completed) / len(completed), 4
            ),
        }

    # ------------------------------------------------------------------
    # Node participation
    # ------------------------------------------------------------------

    def node_participation_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.rounds:
            for node_id in r.node_ids:
                counts[node_id] = counts.get(node_id, 0) + 1
        return dict(sorted(counts.items()))

    def node_participation_rates(self) -> dict[str, float]:
        total = len(self.rounds) or 1
        return {
            node: round(count / total, 4)
            for node, count in self.node_participation_counts().items()
        }

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def full_report(self) -> dict[str, Any]:
        return {
            "summary": self.summary_stats(),
            "accuracy_series": self.accuracy_series(),
            "loss_series": self.loss_series(),
            "f1_series": self.f1_series(),
            "roc_auc_series": self.roc_auc_series(),
            "participation_series": self.participation_series(),
            "node_participation_counts": self.node_participation_counts(),
            "node_participation_rates": self.node_participation_rates(),
            "rounds": [r.to_dict() for r in self.rounds],
        }


# ---------------------------------------------------------------------------
# FL vs Centralized comparison
# ---------------------------------------------------------------------------

class ComparisonReport:
    """Side-by-side comparison of FL and centralized learning metrics."""

    def __init__(
        self,
        fl_metrics: dict[str, float | None],
        centralized_metrics: dict[str, float | None],
    ) -> None:
        self.fl = _round_dict(fl_metrics)
        self.centralized = _round_dict(centralized_metrics)

    def _delta(self, key: str) -> float:
        return round(self.fl.get(key, 0.0) - self.centralized.get(key, 0.0), 6)

    def delta_table(self) -> dict[str, dict[str, float]]:
        all_keys = set(self.fl) | set(self.centralized)
        return {
            key: {
                "federated": self.fl.get(key, 0.0),
                "centralized": self.centralized.get(key, 0.0),
                "delta": self._delta(key),
            }
            for key in sorted(all_keys)
        }

    def privacy_advantage(self) -> str:
        """Return a human-readable summary of privacy vs accuracy trade-off."""
        acc_delta = self._delta("accuracy")
        if abs(acc_delta) <= 0.02:
            return (
                "Federated learning achieves comparable accuracy to centralized "
                "training (Δ accuracy ≤ 2 pp) while preserving full data privacy."
            )
        if acc_delta < 0:
            return (
                f"Federated learning accuracy is {abs(acc_delta):.2%} lower than "
                "centralized, which is acceptable given full data-privacy guarantees."
            )
        return (
            f"Federated learning outperforms centralized by {acc_delta:.2%} "
            "in accuracy, while preserving full data privacy."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "federated": self.fl,
            "centralized": self.centralized,
            "delta_table": self.delta_table(),
            "privacy_advantage": self.privacy_advantage(),
        }


# ---------------------------------------------------------------------------
# JSONL round history reader (for the FL server output file)
# ---------------------------------------------------------------------------

def load_round_history(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL training-round history file written by the FL server."""
    target = Path(path)
    if not target.exists():
        return []
    rounds: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rounds.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rounds
