# Phase 5 — XAI Engine, Analytics, Fairness & Reports

## Status: COMPLETE

---

## Files Generated

### XAI Engine
| File | Description |
|---|---|
| `xai_engine/shap/explainer.py` | SHAP KernelExplainer — summary, waterfall, bar, force plots |
| `xai_engine/lime/explainer.py` | LIME tabular — local plot, HTML, contribution JSON |
| `xai_engine/common.py` | Shared context builder, ArtifactPredictor, reference background |

### Backend XAI Service & API
| File | Description |
|---|---|
| `backend/app/services/xai_service.py` | SHAP/LIME orchestration + XAI report persistence |
| `backend/app/api/v1/xai.py` | REST: generate, get by ID, get by prediction |
| `backend/app/schemas/xai.py` | `XAIGenerateRequest`, `XAIReportRead`, `XAIReportResponse` |

### Analytics Engine
| File | Description |
|---|---|
| `analytics/engine.py` | `FLAnalyticsEngine`, `ComparisonReport`, JSONL loader |
| `analytics/fairness.py` | `GroupFairnessAnalysis`, `FeatureInfluenceComparison`, `FairnessReportBuilder` |
| `backend/app/services/analytics_service.py` | Async DB queries → FL report, comparison, node stats |
| `backend/app/api/v1/analytics.py` | Analytics REST endpoints |

### Report Generation
| File | Description |
|---|---|
| `backend/app/services/report_service.py` | `PDFReportBuilder`, `CSVReportBuilder`, `FairnessCSVBuilder` |
| `backend/app/api/v1/reports.py` | PDF download, CSV bulk export, fairness CSV |

### Training Monitor
| File | Description |
|---|---|
| `backend/app/api/v1/training.py` | FL round list/detail, model registry, node status, cancel |

### Tests
| File | Description |
|---|---|
| `tests/analytics/test_analytics_engine.py` | 30 unit tests — engine, comparison, fairness, feature influence |
| `tests/unit/test_report_service.py` | 11 unit tests — CSV, PDF/HTML, fairness CSV |

---

## API Endpoints Added

### XAI — `/api/v1/xai`
| Method | Path | Permission |
|---|---|---|
| `POST` | `/reports/{prediction_id}` | `xai:view` |
| `GET` | `/reports/{report_id}` | `xai:view` |
| `GET` | `/predictions/{prediction_id}` | `xai:view` |

### Analytics — `/api/v1/analytics`
| Method | Path | Permission |
|---|---|---|
| `GET` | `/fl/report` | `metrics:view` |
| `GET` | `/fl/rounds` | `metrics:view` |
| `GET` | `/fl/nodes` | `metrics:view` |
| `GET` | `/comparison` | `models:compare` |
| `GET` | `/predictions/stats` | `metrics:view` |
| `POST` | `/fairness` | `fairness:analyze` |

### Reports — `/api/v1/reports`
| Method | Path | Permission |
|---|---|---|
| `GET` | `/predictions/{id}/pdf` | `reports:download` |
| `GET` | `/predictions/csv` | `reports:download` |
| `POST` | `/fairness/csv` | `fairness:analyze` |

### Training Monitor — `/api/v1/training`
| Method | Path | Permission |
|---|---|---|
| `GET` | `/rounds` | `metrics:view` |
| `GET` | `/rounds/{id}` | `metrics:view` |
| `GET` | `/models` | `metrics:view` |
| `GET` | `/models/active` | `metrics:view` |
| `GET` | `/nodes` | `hospital_nodes:monitor` |
| `POST` | `/rounds/{id}/cancel` | `fl_rounds:control` |

---

## SHAP Artifacts (per prediction)
- `summary_plot.png` — Beeswarm global importance
- `bar_plot.png` — Mean |SHAP| bar chart
- `waterfall_plot.png` — Single-instance waterfall
- `force_plot.html` — Interactive force plot
- `feature_ranking.json` — Ranked contributions
- `manifest.json` — File paths manifest

## LIME Artifacts (per prediction)
- `local_explanation.png` — Local contribution bar chart
- `local_explanation.html` — Interactive LIME HTML
- `feature_contributions.json` — Ranked contributions
- `manifest.json` — File paths manifest

---

## Fairness Metrics
| Metric | Threshold |
|---|---|
| Disparate Impact | < 0.80 triggers bias flag |
| Statistical Parity Difference | Informational |
| Equalized Odds (max ΔTPR/FPR) | > 0.10 triggers bias flag |

---

## Privacy Design
- No raw patient data leaves hospitals for XAI
- SHAP/LIME background matrix built from artifact preprocessing metadata only
- `KernelExplainer` works without raw training data

---

## Verification Commands
```powershell
python -m compileall -q analytics backend tests
$env:PYTHONPATH = "$env:TEMP\fedpedia-phase1-deps;."
python -m pytest tests/unit tests/api tests/fl tests/ml tests/analytics -q
```
