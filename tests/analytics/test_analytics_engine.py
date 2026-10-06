"""Unit tests for the analytics engine and fairness module."""

import math

import pytest

from analytics.engine import (
    ComparisonReport,
    FLAnalyticsEngine,
    RoundSummary,
    load_round_history,
)
from analytics.fairness import (
    FairnessReportBuilder,
    FeatureInfluenceComparison,
    GroupFairnessAnalysis,
    disparate_impact,
    equalized_odds_difference,
    statistical_parity_difference,
)

# ---------------------------------------------------------------------------
# RoundSummary
# ---------------------------------------------------------------------------


def _make_round(
    round_number: int = 1,
    *,
    accuracy: float = 0.80,
    loss: float = 0.30,
    participating_clients: int = 3,
    total_clients: int = 3,
    nodes: list | None = None,
    status: str = "completed",
) -> dict:
    return {
        "round_number": round_number,
        "accuracy": accuracy,
        "precision": 0.78,
        "recall": 0.82,
        "f1": 0.80,
        "roc_auc": 0.85,
        "loss": loss,
        "participating_clients": participating_clients,
        "total_clients": total_clients,
        "participating_nodes": nodes or ["node_1", "node_2", "node_3"],
        "aggregation_strategy": "fedavg",
        "status": status,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }


def test_round_summary_participation_rate() -> None:
    r = RoundSummary(_make_round(participating_clients=2, total_clients=3))
    assert r.participation_rate() == round(2 / 3, 4)


def test_round_summary_to_dict_keys() -> None:
    r = RoundSummary(_make_round())
    d = r.to_dict()
    for key in ("round_number", "accuracy", "loss", "f1", "participation_rate", "node_ids"):
        assert key in d


# ---------------------------------------------------------------------------
# FLAnalyticsEngine
# ---------------------------------------------------------------------------


@pytest.fixture()
def fl_engine() -> FLAnalyticsEngine:
    rounds = [
        _make_round(1, accuracy=0.70, loss=0.50),
        _make_round(2, accuracy=0.75, loss=0.40),
        _make_round(3, accuracy=0.80, loss=0.30, nodes=["node_1", "node_2"]),
    ]
    return FLAnalyticsEngine(rounds)


def test_accuracy_series_length(fl_engine: FLAnalyticsEngine) -> None:
    assert len(fl_engine.accuracy_series()) == 3


def test_loss_decreasing_final(fl_engine: FLAnalyticsEngine) -> None:
    series = fl_engine.loss_series()
    assert series[-1]["loss"] < series[0]["loss"]


def test_summary_stats_keys(fl_engine: FLAnalyticsEngine) -> None:
    stats = fl_engine.summary_stats()
    assert stats["completed_rounds"] == 3
    assert "accuracy" in stats
    assert "f1" in stats


def test_node_participation_counts(fl_engine: FLAnalyticsEngine) -> None:
    counts = fl_engine.node_participation_counts()
    assert counts["node_1"] == 3
    assert counts["node_3"] == 2  # only in rounds 1 and 2


def test_node_participation_rates(fl_engine: FLAnalyticsEngine) -> None:
    rates = fl_engine.node_participation_rates()
    assert rates["node_3"] == round(2 / 3, 4)


def test_fl_full_report_structure(fl_engine: FLAnalyticsEngine) -> None:
    report = fl_engine.full_report()
    for key in (
        "summary",
        "accuracy_series",
        "loss_series",
        "f1_series",
        "roc_auc_series",
        "participation_series",
        "node_participation_counts",
        "node_participation_rates",
        "rounds",
    ):
        assert key in report


# ---------------------------------------------------------------------------
# ComparisonReport
# ---------------------------------------------------------------------------


def test_comparison_delta_table() -> None:
    report = ComparisonReport(
        fl_metrics={"accuracy": 0.82, "f1": 0.80},
        centralized_metrics={"accuracy": 0.85, "f1": 0.83},
    )
    table = report.delta_table()
    assert "accuracy" in table
    assert math.isclose(table["accuracy"]["delta"], 0.82 - 0.85, rel_tol=1e-5)


def test_comparison_privacy_advantage_comparable() -> None:
    report = ComparisonReport(
        fl_metrics={"accuracy": 0.81},
        centralized_metrics={"accuracy": 0.82},
    )
    text = report.privacy_advantage()
    assert "comparable" in text.lower()


def test_comparison_to_dict_keys() -> None:
    report = ComparisonReport(fl_metrics={"accuracy": 0.80}, centralized_metrics={"accuracy": 0.85})
    d = report.to_dict()
    for key in ("federated", "centralized", "delta_table", "privacy_advantage"):
        assert key in d


# ---------------------------------------------------------------------------
# load_round_history
# ---------------------------------------------------------------------------


def test_load_round_history_missing(tmp_path) -> None:
    result = load_round_history(tmp_path / "nonexistent.jsonl")
    assert result == []


def test_load_round_history_valid(tmp_path) -> None:
    import json

    path = tmp_path / "history.jsonl"
    path.write_text(
        json.dumps({"round_number": 1, "accuracy": 0.80}) + "\n"
        + json.dumps({"round_number": 2, "accuracy": 0.85}) + "\n",
        encoding="utf-8",
    )
    rounds = load_round_history(path)
    assert len(rounds) == 2
    assert rounds[1]["accuracy"] == 0.85


# ---------------------------------------------------------------------------
# Fairness primitives
# ---------------------------------------------------------------------------


def test_disparate_impact_above_threshold() -> None:
    di = disparate_impact(positive_rate_privileged=0.60, positive_rate_unprivileged=0.55)
    assert di > 0.80  # no bias


def test_disparate_impact_below_threshold() -> None:
    di = disparate_impact(positive_rate_privileged=0.60, positive_rate_unprivileged=0.40)
    assert di < 0.80  # bias flagged


def test_statistical_parity_difference() -> None:
    spd = statistical_parity_difference(0.60, 0.40)
    assert math.isclose(spd, -0.20, rel_tol=1e-5)


def test_equalized_odds_difference() -> None:
    result = equalized_odds_difference(
        tpr_privileged=0.80,
        tpr_unprivileged=0.65,
        fpr_privileged=0.15,
        fpr_unprivileged=0.20,
    )
    assert math.isclose(result["tpr_difference"], 0.15, rel_tol=1e-5)
    assert result["max_difference"] >= result["tpr_difference"]


# ---------------------------------------------------------------------------
# GroupFairnessAnalysis
# ---------------------------------------------------------------------------


@pytest.fixture()
def group_analysis() -> GroupFairnessAnalysis:
    return GroupFairnessAnalysis(
        feature_name="sex",
        privileged_group="male",
        groups={
            "male": {
                "labels": [1, 0, 1, 0, 1, 1, 0, 0, 1, 0],
                "predictions": [1, 0, 1, 0, 1, 0, 0, 0, 1, 0],
                "positive_rate": 0.60,
            },
            "female": {
                "labels": [1, 0, 1, 0, 0, 0, 1, 1, 0, 0],
                "predictions": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                "positive_rate": 0.30,
            },
        },
    )


def test_group_metrics_present(group_analysis: GroupFairnessAnalysis) -> None:
    metrics = group_analysis.group_metrics()
    assert "male" in metrics
    assert "female" in metrics
    for key in ("accuracy", "precision", "recall", "fpr"):
        assert key in metrics["male"]


def test_disparate_impact_table(group_analysis: GroupFairnessAnalysis) -> None:
    table = group_analysis.disparate_impact_table()
    # female positive_rate=0.30 / male=0.60 = 0.50 → below 0.80 → bias
    assert "female" in table
    assert table["female"] < 0.80


def test_bias_detected(group_analysis: GroupFairnessAnalysis) -> None:
    assert group_analysis.overall_bias_detected() is True


def test_bias_flags_structure(group_analysis: GroupFairnessAnalysis) -> None:
    flags = group_analysis.bias_flags()
    assert "female" in flags


def test_group_full_report_structure(group_analysis: GroupFairnessAnalysis) -> None:
    report = group_analysis.report()
    for key in (
        "feature_name",
        "privileged_group",
        "group_metrics",
        "disparate_impact",
        "statistical_parity",
        "equalized_odds",
        "bias_flags",
        "bias_detected",
    ):
        assert key in report


# ---------------------------------------------------------------------------
# FeatureInfluenceComparison
# ---------------------------------------------------------------------------


@pytest.fixture()
def feature_comparison() -> FeatureInfluenceComparison:
    fl = [
        {"feature": "age", "abs_contribution": 0.35},
        {"feature": "glucose", "abs_contribution": 0.25},
        {"feature": "bmi", "abs_contribution": 0.15},
    ]
    cl = [
        {"feature": "age", "abs_contribution": 0.30},
        {"feature": "glucose", "abs_contribution": 0.28},
        {"feature": "bmi", "abs_contribution": 0.10},
    ]
    return FeatureInfluenceComparison(federated_ranking=fl, centralized_ranking=cl)


def test_rank_shift_table_length(feature_comparison: FeatureInfluenceComparison) -> None:
    table = feature_comparison.rank_shift_table()
    assert len(table) == 3


def test_rank_shift_has_delta(feature_comparison: FeatureInfluenceComparison) -> None:
    table = feature_comparison.rank_shift_table()
    for row in table:
        assert "importance_delta" in row
        assert "fl_rank" in row


def test_top_consistent_features(feature_comparison: FeatureInfluenceComparison) -> None:
    top = feature_comparison.top_consistent_features(n=2)
    assert len(top) == 2


# ---------------------------------------------------------------------------
# FairnessReportBuilder
# ---------------------------------------------------------------------------


def test_fairness_report_builder_no_bias() -> None:
    analysis = GroupFairnessAnalysis(
        feature_name="age_group",
        privileged_group="adult",
        groups={
            "adult": {
                "labels": [1, 0, 1, 0],
                "predictions": [1, 0, 1, 0],
                "positive_rate": 0.60,
            },
            "senior": {
                "labels": [1, 0, 1, 0],
                "predictions": [1, 0, 1, 0],
                "positive_rate": 0.55,
            },
        },
    )
    report = FairnessReportBuilder().add_group_analysis(analysis).build()
    assert "overall_bias_detected" in report
    assert "recommendation" in report


# ---------------------------------------------------------------------------
# Ground-truth-free fairness (real clinical predictions without labels)
# ---------------------------------------------------------------------------


def test_group_analysis_without_labels_omits_label_metrics() -> None:
    analysis = GroupFairnessAnalysis(
        feature_name="sex",
        privileged_group="male",
        groups={
            "male": {"predictions": [1, 0, 1, 1], "positive_rate": 0.75},
            "female": {"predictions": [0, 0, 1, 0], "positive_rate": 0.25},
        },
    )
    metrics = analysis.group_metrics()
    assert metrics["male"]["positive_rate"] == 0.75
    assert "accuracy" not in metrics["male"]
    assert "recall" not in metrics["male"]
    assert analysis.equalized_odds_table() == {}
    assert analysis.disparate_impact_table()["female"] == pytest.approx(0.25 / 0.75)
    report = analysis.report()
    assert report["ground_truth_available"] is False
    # Bias still detectable from positive rates alone
    assert report["bias_detected"] is True


def test_group_analysis_with_labels_still_reports_full_metrics() -> None:
    analysis = GroupFairnessAnalysis(
        feature_name="sex",
        privileged_group="male",
        groups={
            "male": {"labels": [1, 0, 1, 0], "predictions": [1, 0, 1, 0]},
            "female": {"labels": [1, 0, 1, 0], "predictions": [0, 0, 1, 0]},
        },
    )
    metrics = analysis.group_metrics()
    assert "accuracy" in metrics["male"]
    assert metrics["male"]["accuracy"] == 1.0
    assert analysis.report()["ground_truth_available"] is True
    assert analysis.equalized_odds_table() != {}


def test_report_builder_without_data_is_honest() -> None:
    report = FairnessReportBuilder().build(data_available=False)
    assert report["data_available"] is False
    assert report["overall_bias_detected"] is False
    assert report["group_analyses"] == []
    assert "No stored prediction data" in report["recommendation"]


def test_report_builder_defaults_to_data_available() -> None:
    report = FairnessReportBuilder().build()
    assert report["data_available"] is True
