"""Report generation service — PDF and CSV export for predictions and XAI results."""

from __future__ import annotations

import csv
import io
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.models.enums import DatasetType, RiskLevel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, max_len: int = 120) -> str:
    return str(value or "")[:max_len]


def _risk_label(risk_level: str | RiskLevel) -> str:
    mapping = {
        RiskLevel.LOW.value: "Low Risk",
        RiskLevel.MODERATE.value: "Moderate Risk",
        RiskLevel.HIGH.value: "High Risk",
    }
    return mapping.get(str(risk_level), str(risk_level).title())


# ---------------------------------------------------------------------------
# CSV Report
# ---------------------------------------------------------------------------

class CSVReportBuilder:
    """Build a CSV export of one or more predictions."""

    COLUMNS = [
        "report_generated_at",
        "prediction_id",
        "patient_id",
        "dataset_type",
        "model_source",
        "prediction",
        "risk_level",
        "probability",
        "doctor_notes",
        "shap_top_features",
        "lime_top_features",
        "xai_status",
        "created_at",
    ]

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def add_prediction_row(
        self,
        *,
        prediction_id: uuid.UUID,
        patient_id: uuid.UUID,
        dataset_type: str,
        model_source: str,
        prediction: int,
        risk_level: str,
        probability: float,
        doctor_notes: str | None = None,
        shap_top_features: list[str] | None = None,
        lime_top_features: list[str] | None = None,
        xai_status: str | None = None,
        created_at: datetime | None = None,
    ) -> CSVReportBuilder:
        self._rows.append(
            {
                "report_generated_at": _now_iso(),
                "prediction_id": str(prediction_id),
                "patient_id": str(patient_id),
                "dataset_type": dataset_type,
                "model_source": model_source,
                "prediction": prediction,
                "risk_level": risk_level,
                "probability": round(probability, 6),
                "doctor_notes": _safe_str(doctor_notes),
                "shap_top_features": "; ".join(shap_top_features or []),
                "lime_top_features": "; ".join(lime_top_features or []),
                "xai_status": xai_status or "",
                "created_at": created_at.isoformat() if created_at else "",
            }
        )
        return self

    def build_bytes(self) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.COLUMNS)
        writer.writeheader()
        writer.writerows(self._rows)
        return buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.build_bytes())
        return target


# ---------------------------------------------------------------------------
# Plain-text PDF via reportlab (or fallback HTML if unavailable)
# ---------------------------------------------------------------------------

def _try_import_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


class PDFReportBuilder:
    """Build a clinical PDF report for a single prediction with SHAP/LIME results."""

    def __init__(
        self,
        *,
        prediction_id: uuid.UUID,
        patient_id: uuid.UUID,
        dataset_type: str | DatasetType,
        model_source: str,
        prediction: int,
        risk_level: str | RiskLevel,
        probability: float,
        doctor_notes: str | None = None,
        feature_ranking: list[dict[str, Any]] | None = None,
        local_contributions: list[dict[str, Any]] | None = None,
        top_shap_features: list[str] | None = None,
        top_lime_features: list[str] | None = None,
        model_version: str | None = None,
        shap_plot_path: str | None = None,
        lime_plot_path: str | None = None,
    ) -> None:
        self.prediction_id = prediction_id
        self.patient_id = patient_id
        self.dataset_type = str(dataset_type)
        self.model_source = model_source
        self.prediction = prediction
        self.risk_level = str(risk_level)
        self.probability = probability
        self.doctor_notes = doctor_notes or ""
        self.feature_ranking = feature_ranking or []
        self.local_contributions = local_contributions or []
        self.top_shap_features = top_shap_features or []
        self.top_lime_features = top_lime_features or []
        self.model_version = model_version or "unknown"
        self.shap_plot_path = shap_plot_path
        self.lime_plot_path = lime_plot_path
        self.generated_at = _now_iso()

    # ------------------------------------------------------------------
    # Reportlab PDF
    # ------------------------------------------------------------------

    def _build_with_reportlab(self, output_path: Path) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=18,
            textColor=colors.HexColor("#1a3c5e"),
            spaceAfter=12,
        )
        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#2563eb"),
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = styles["BodyText"]
        risk_color = {
            "high": colors.HexColor("#dc2626"),
            "moderate": colors.HexColor("#d97706"),
            "low": colors.HexColor("#16a34a"),
        }.get(self.risk_level.lower(), colors.black)

        story = []

        # Title
        story.append(Paragraph("FedPedia-XAI Clinical Prediction Report", title_style))
        story.append(Spacer(1, 0.3 * cm))

        # Meta table
        meta_data = [
            ["Generated At", self.generated_at],
            ["Prediction ID", str(self.prediction_id)],
            ["Patient ID", str(self.patient_id)],
            ["Dataset", self.dataset_type.replace("_", " ").title()],
            ["Model Source", self.model_source.replace("_", " ").title()],
            ["Model Version", self.model_version],
        ]
        meta_table = Table(meta_data, colWidths=[4 * cm, 13 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.5 * cm))

        # Prediction result
        story.append(Paragraph("Prediction Result", heading_style))
        result_label = "POSITIVE" if self.prediction == 1 else "NEGATIVE"
        result_data = [
            ["Outcome", result_label],
            ["Risk Level", _risk_label(self.risk_level)],
            ["Probability", f"{self.probability:.2%}"],
        ]
        result_table = Table(result_data, colWidths=[4 * cm, 13 * cm])
        result_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (1, 1), (1, 1), risk_color),
                    ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(result_table)
        story.append(Spacer(1, 0.4 * cm))

        # Doctor notes
        if self.doctor_notes:
            story.append(Paragraph("Doctor Notes", heading_style))
            story.append(Paragraph(self.doctor_notes, body_style))
            story.append(Spacer(1, 0.4 * cm))

        # SHAP top features
        if self.top_shap_features:
            story.append(Paragraph("SHAP — Global Feature Importance", heading_style))
            shap_rows = [["Rank", "Feature"]] + [
                [str(i + 1), feat] for i, feat in enumerate(self.top_shap_features[:10])
            ]
            shap_table = Table(shap_rows, colWidths=[2 * cm, 15 * cm])
            shap_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(shap_table)

            if (
                self.shap_plot_path
                and Path(self.shap_plot_path).exists()
            ):
                story.append(Spacer(1, 0.3 * cm))
                story.append(
                    Image(self.shap_plot_path, width=14 * cm, height=8 * cm)
                )
            story.append(Spacer(1, 0.4 * cm))

        # LIME top features
        if self.top_lime_features:
            story.append(Paragraph("LIME — Local Feature Contribution", heading_style))
            lime_rows = [["Rank", "Feature"]] + [
                [str(i + 1), feat] for i, feat in enumerate(self.top_lime_features[:10])
            ]
            lime_table = Table(lime_rows, colWidths=[2 * cm, 15 * cm])
            lime_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(lime_table)

            if (
                self.lime_plot_path
                and Path(self.lime_plot_path).exists()
            ):
                story.append(Spacer(1, 0.3 * cm))
                story.append(
                    Image(self.lime_plot_path, width=14 * cm, height=8 * cm)
                )
            story.append(Spacer(1, 0.4 * cm))

        # Feature ranking detail table
        if self.feature_ranking:
            story.append(Paragraph("SHAP Feature Importance Detail", heading_style))
            detail_rows = [["Feature", "Value", "Contribution"]] + [
                [
                    _safe_str(r.get("feature")),
                    f"{float(r.get('value', 0)):.4f}",
                    f"{float(r.get('contribution', 0)):+.4f}",
                ]
                for r in self.feature_ranking[:15]
            ]
            detail_table = Table(detail_rows, colWidths=[6 * cm, 4 * cm, 7 * cm])
            detail_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(detail_table)

        # Footer
        story.append(Spacer(1, 0.8 * cm))
        story.append(
            Paragraph(
                "<i>This report is AI-generated and is intended to assist, not replace, "
                "clinical judgment. All predictions should be reviewed by a qualified "
                "clinician.</i>",
                body_style,
            )
        )

        doc.build(story)

    # ------------------------------------------------------------------
    # HTML fallback (when reportlab is not installed)
    # ------------------------------------------------------------------

    def _build_html_fallback(self, output_path: Path) -> None:
        risk_colours = {"high": "#dc2626", "moderate": "#d97706", "low": "#16a34a"}
        risk_colour = risk_colours.get(self.risk_level.lower(), "#374151")

        def _rows(items: list[dict[str, Any]], keys: list[str]) -> str:
            return "".join(
                "<tr>" + "".join(f"<td>{_safe_str(row.get(k))}</td>" for k in keys) + "</tr>"
                for row in items
            )

        html = textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8"/>
          <title>FedPedia-XAI Clinical Report</title>
          <style>
            body{{font-family:Arial,sans-serif;margin:40px;color:#1f2937}}
            h1{{color:#1a3c5e}}h2{{color:#2563eb;border-bottom:1px solid #e5e7eb;padding-bottom:4px}}
            table{{border-collapse:collapse;width:100%;margin-bottom:16px}}
            th,td{{border:1px solid #d1d5db;padding:6px 10px;font-size:13px}}
            th{{background:#1a3c5e;color:#fff;text-align:left}}
            tr:nth-child(even){{background:#f9fafb}}
            .risk{{font-weight:bold;color:{risk_colour}}}
            .footer{{margin-top:32px;font-size:11px;color:#6b7280;font-style:italic}}
          </style>
        </head>
        <body>
          <h1>FedPedia-XAI Clinical Prediction Report</h1>
          <h2>Report Metadata</h2>
          <table>
            <tr><th>Generated At</th><td>{self.generated_at}</td></tr>
            <tr><th>Prediction ID</th><td>{self.prediction_id}</td></tr>
            <tr><th>Patient ID</th><td>{self.patient_id}</td></tr>
            <tr><th>Dataset</th><td>{self.dataset_type.replace("_"," ").title()}</td></tr>
            <tr><th>Model Source</th><td>{self.model_source.replace("_"," ").title()}</td></tr>
            <tr><th>Model Version</th><td>{self.model_version}</td></tr>
          </table>
          <h2>Prediction Result</h2>
          <table>
            <tr><th>Outcome</th><td>{"POSITIVE" if self.prediction==1 else "NEGATIVE"}</td></tr>
            <tr><th>Risk Level</th><td class="risk">{_risk_label(self.risk_level)}</td></tr>
            <tr><th>Probability</th><td>{self.probability:.2%}</td></tr>
          </table>
          {"<h2>Doctor Notes</h2><p>" + self.doctor_notes + "</p>" if self.doctor_notes else ""}
          {"<h2>SHAP — Top Features</h2><table><tr><th>Rank</th><th>Feature</th></tr>" + "".join(f"<tr><td>{i+1}</td><td>{f}</td></tr>" for i, f in enumerate(self.top_shap_features[:10])) + "</table>" if self.top_shap_features else ""}
          {"<h2>LIME — Top Features</h2><table><tr><th>Rank</th><th>Feature</th></tr>" + "".join(f"<tr><td>{i+1}</td><td>{f}</td></tr>" for i,f in enumerate(self.top_lime_features[:10])) + "</table>" if self.top_lime_features else ""}
          {"<h2>SHAP Feature Importance Detail</h2><table><tr><th>Feature</th><th>Value</th><th>Contribution</th></tr>" + _rows(self.feature_ranking[:15], ["feature","value","contribution"]) + "</table>" if self.feature_ranking else ""}
          <p class="footer">This report is AI-generated and is intended to assist, not replace,
          clinical judgment. All predictions should be reviewed by a qualified clinician.</p>
        </body>
        </html>
        """)
        output_path.write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def save_pdf(self, output_path: str | Path) -> Path:
        """Save as PDF (reportlab) or HTML fallback. Returns the written path."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if _try_import_reportlab():
            self._build_with_reportlab(target)
        else:
            # Emit HTML with .html extension when reportlab unavailable
            target = target.with_suffix(".html")
            self._build_html_fallback(target)
        return target


# ---------------------------------------------------------------------------
# Fairness report CSV
# ---------------------------------------------------------------------------

class FairnessCSVBuilder:
    """Export a fairness report to CSV."""

    COLUMNS = [
        "feature_name",
        "group",
        "count",
        "accuracy",
        "precision",
        "recall",
        "fpr",
        "disparate_impact",
        "statistical_parity",
        "bias_flags",
    ]

    def __init__(self, fairness_report: dict) -> None:
        self._report = fairness_report

    def build_bytes(self) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.COLUMNS)
        writer.writeheader()

        for analysis in self._report.get("group_analyses", []):
            feature = analysis.get("feature_name", "")
            group_metrics = analysis.get("group_metrics", {})
            di_table = analysis.get("disparate_impact", {})
            sp_table = analysis.get("statistical_parity", {})
            flags_table = analysis.get("bias_flags", {})

            for group, metrics in group_metrics.items():
                writer.writerow(
                    {
                        "feature_name": feature,
                        "group": group,
                        "count": metrics.get("count", ""),
                        "accuracy": metrics.get("accuracy", ""),
                        "precision": metrics.get("precision", ""),
                        "recall": metrics.get("recall", ""),
                        "fpr": metrics.get("fpr", ""),
                        "disparate_impact": di_table.get(group, "N/A"),
                        "statistical_parity": sp_table.get(group, "N/A"),
                        "bias_flags": "; ".join(flags_table.get(group, [])),
                    }
                )
        return buf.getvalue().encode("utf-8-sig")
