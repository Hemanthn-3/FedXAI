# Prediction Engine Guide

## Phase 4 scope

Phase 4 implements versioned inference:

- active global model lookup;
- SHA-256 checksum verification;
- PyTorch model loading;
- feature validation and aliases;
- probability, binary class, and risk-level generation;
- persisted prediction records;
- doctor-facing prediction APIs.

SHAP and LIME explanations begin in Phase 5.

## Input contract

The prediction engine reads the active `global_models` row for the selected
dataset and source. The artifact defines required `feature_names`. The request
must provide all required features.

Compact clinical model example:

```json
{
  "age": 52,
  "bp": 130,
  "cholesterol": 240,
  "glucose": 115
}
```

The engine accepts safe aliases such as `blood_pressure` for `bp` and `chol`
for `cholesterol`.

If a federated Heart Disease artifact expects the complete training schema,
the request must include:

```text
age, sex, cp, trestbps, chol, fbs, thalach, exang, oldpeak
```

The engine does not invent missing clinical values.

## Output contract

```json
{
  "prediction": 1,
  "risk": "High",
  "probability": 0.92
}
```

The API response also includes model version, dataset type, model source,
required feature names, and warnings.

## Risk thresholds

- `High`: probability >= 0.75
- `Moderate`: probability >= 0.40 and < 0.75
- `Low`: probability < 0.40

## Persistence

`POST /predictions` persists:

- patient ID;
- global model ID;
- dataset type;
- federated/centralized model source;
- normalized input feature snapshot;
- probability;
- risk level;
- binary prediction;
- optional doctor notes.

Preview predictions from `POST /predictions/preview` are audited but not stored
as clinical prediction records.

## Artifact compatibility

Phase 4 model artifacts include `feature_names` and `preprocessing` metadata.
Older Phase 3 artifacts remain loadable if their input dimension matches a
known dataset schema. If metadata is missing and cannot be inferred safely, the
engine refuses inference.
