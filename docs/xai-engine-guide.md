# XAI Engine Guide

## Phase 5 scope

Phase 5 implements explainability for persisted predictions:

- SHAP summary plot;
- SHAP waterfall plot;
- SHAP bar plot;
- SHAP force plot;
- SHAP feature ranking;
- LIME local explanation;
- LIME feature contribution list;
- LIME top influencing features;
- automatic artifact storage;
- persisted `XAI_REPORTS` metadata;
- scoped explainability API endpoints.

## Privacy boundary

The XAI engine does not centralize raw hospital training rows. It explains a
persisted prediction using:

- the prediction feature snapshot already stored for clinical provenance;
- the versioned global model artifact;
- model preprocessing metadata;
- a deterministic synthetic reference matrix derived from model metadata and
  the current prediction.

This keeps SHAP/LIME generation compatible with the federated privacy model.

## Artifact layout

For prediction `<prediction-id>` the engine writes:

```text
reports/xai/<prediction-id>/
├── shap/
│   ├── summary_plot.png
│   ├── waterfall_plot.png
│   ├── bar_plot.png
│   ├── force_plot.html
│   ├── feature_ranking.json
│   └── manifest.json
└── lime/
    ├── local_explanation.png
    ├── local_explanation.html
    ├── feature_contributions.json
    └── manifest.json
```

`XAI_REPORTS.shap_path` and `XAI_REPORTS.lime_path` store the corresponding
directories. Feature ranking and local contributions are also persisted in
PostgreSQL as JSONB for dashboard rendering.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/xai/reports/{prediction_id}` | Generate or reuse SHAP/LIME report |
| GET | `/api/v1/xai/reports/{report_id}` | Read XAI report by report ID |
| GET | `/api/v1/xai/predictions/{prediction_id}` | Read XAI report by prediction ID |

Only users with `xai:view` may access these endpoints. Hospital scoping is
enforced through the prediction's patient record.

## Generation behavior

By default, generation is idempotent: if a completed report exists, it is
returned without regenerating files. Send `{"regenerate": true}` to replace
stored artifacts.

```json
{
  "regenerate": false,
  "background_size": 48
}
```

## Output highlights

The API returns:

- SHAP directory path;
- LIME directory path;
- SHAP feature ranking;
- LIME local contributions;
- top SHAP features;
- top LIME features;
- generation status.
