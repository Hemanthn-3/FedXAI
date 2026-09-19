# Phase 4 Verification

## Acceptance criteria

- Prediction engine loads checksummed PyTorch artifacts.
- Missing or non-numeric features are rejected.
- Compact example input returns `prediction`, `risk`, and `probability`.
- Active model lookup is ready for PostgreSQL-backed inference.
- Persisted predictions are tied to patients and global models.
- Doctor-scoped prediction APIs are present in OpenAPI.
- Compile, lint, ML tests, API tests, and full regression tests pass.

## Verification commands

```powershell
python -m compileall -q backend fl_server hospital_nodes xai_engine analytics database tests
ruff check backend fl_server hospital_nodes xai_engine analytics database tests
pytest tests/unit tests/api tests/fl tests/ml -q
```

Live prediction persistence requires PostgreSQL plus at least one active
`global_models` row pointing at a valid artifact. Unit tests validate the
inference path using temporary model artifacts.
