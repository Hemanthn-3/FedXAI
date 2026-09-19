"""Unit tests for the report generation service (CSV and PDF/HTML)."""

import csv
import io
import uuid
from pathlib import Path

import pytest

from backend.app.services.report_service import (
    CSVReportBuilder,
    FairnessCSVBuilder,
    PDFReportBuilder,
)

# ---------------------------------------------------------------------------
# CSV Report
# ---------------------------------------------------------------------------


@pytest.fixture()
def csv_builder() -> CSVReportBuilder:
    builder = CSVReportBuilder()
    builder.add_prediction_row(
        prediction_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        dataset_type="heart_disease",
        model_source="federated",
        prediction=1,
        risk_level="high",
        probability=0.92,
        doctor_notes="Monitor closely.",
        shap_top_features=["age", "cholesterol"],
        lime_top_features=["age", "bp"],
        xai_status="completed",
    )
    return builder


def test_csv_has_header(csv_builder: CSVReportBuilder) -> None:
    raw = csv_builder.build_bytes().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    assert reader.fieldnames is not None
    assert "prediction_id" in reader.fieldnames
    assert "risk_level" in reader.fieldnames


def test_csv_has_one_row(csv_builder: CSVReportBuilder) -> None:
    raw = csv_builder.build_bytes().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["risk_level"] == "high"
    assert rows[0]["shap_top_features"] == "age; cholesterol"


def test_csv_save(tmp_path: Path, csv_builder: CSVReportBuilder) -> None:
    out = tmp_path / "report.csv"
    saved = csv_builder.save(out)
    assert saved.exists()
    assert saved.stat().st_size > 0


def test_csv_multiple_rows() -> None:
    builder = CSVReportBuilder()
    for _ in range(5):
        builder.add_prediction_row(
            prediction_id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            dataset_type="diabetes",
            model_source="federated",
            prediction=0,
            risk_level="low",
            probability=0.12,
        )
    raw = builder.build_bytes().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    assert len(list(reader)) == 5


# ---------------------------------------------------------------------------
# PDF / HTML Report
# ---------------------------------------------------------------------------


@pytest.fixture()
def pdf_builder() -> PDFReportBuilder:
    return PDFReportBuilder(
        prediction_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        dataset_type="heart_disease",
        model_source="federated",
        prediction=1,
        risk_level="high",
        probability=0.91,
        doctor_notes="Refer for stress test.",
        top_shap_features=["age", "cholesterol", "bp"],
        top_lime_features=["age", "glucose"],
        feature_ranking=[
            {"feature": "age", "value": 52.0, "contribution": 0.25},
            {"feature": "cholesterol", "value": 240.0, "contribution": 0.18},
        ],
        model_version="v3",
    )


def test_pdf_or_html_saved(tmp_path: Path, pdf_builder: PDFReportBuilder) -> None:
    output = tmp_path / "report.pdf"
    saved = pdf_builder.save_pdf(output)
    assert saved.exists()
    assert saved.stat().st_size > 0


def test_html_fallback_contains_prediction_id(tmp_path: Path, pdf_builder: PDFReportBuilder) -> None:
    """Verify HTML fallback path by monkey-patching reportlab import."""
    import backend.app.services.report_service as rs

    original = rs._try_import_reportlab  # noqa: SLF001
    try:
        rs._try_import_reportlab = lambda: False  # noqa: SLF001
        output = tmp_path / "report.pdf"
        saved = pdf_builder.save_pdf(output)
        assert saved.suffix == ".html"
        html = saved.read_text(encoding="utf-8")
        assert "FedPedia-XAI" in html
        assert "POSITIVE" in html
        assert "age" in html.lower()
    finally:
        rs._try_import_reportlab = original  # noqa: SLF001


def test_html_fallback_risk_level(tmp_path: Path, pdf_builder: PDFReportBuilder) -> None:
    import backend.app.services.report_service as rs

    rs._try_import_reportlab = lambda: False  # noqa: SLF001
    try:
        saved = pdf_builder.save_pdf(tmp_path / "report.pdf")
        html = saved.read_text(encoding="utf-8")
        assert "High Risk" in html
    finally:
        rs._try_import_reportlab = lambda: True  # noqa: SLF001


# ---------------------------------------------------------------------------
# Fairness CSV
# ---------------------------------------------------------------------------


def test_fairness_csv_output() -> None:
    fairness_report = {
        "overall_bias_detected": True,
        "group_analyses": [
            {
                "feature_name": "sex",
                "privileged_group": "male",
                "group_metrics": {
                    "male": {"count": 50, "accuracy": 0.90, "precision": 0.88, "recall": 0.91, "fpr": 0.08},
                    "female": {"count": 40, "accuracy": 0.78, "precision": 0.75, "recall": 0.80, "fpr": 0.15},
                },
                "disparate_impact": {"female": 0.65},
                "statistical_parity": {"female": -0.20},
                "bias_flags": {"female": ["Disparate impact: 0.650 < 0.80"]},
            }
        ],
    }
    csv_bytes = FairnessCSVBuilder(fairness_report).build_bytes()
    raw = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    assert len(rows) == 2
    female_row = next(r for r in rows if r["group"] == "female")
    assert "Disparate" in female_row["bias_flags"]
    assert float(female_row["disparate_impact"]) < 0.80


def test_fairness_csv_no_analyses() -> None:
    csv_bytes = FairnessCSVBuilder({}).build_bytes()
    raw = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    assert list(reader) == []
