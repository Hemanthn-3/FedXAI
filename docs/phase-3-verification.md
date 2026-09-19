# Phase 3 Verification

## Acceptance criteria

- Flower server strategy imports and creates initial parameters.
- Dataset loaders validate all supported schemas and preprocess hospital-local
  CSV files.
- Hospital clients train locally and return only model parameters and scalar
  metrics.
- FedAvg and Weighted FedAvg produce expected aggregate tensors.
- Global model artifacts are saved with SHA-256 checksums.
- Training-round metrics are written to JSONL.
- `hospital_1`, `hospital_2`, and `hospital_3` entrypoints exist.
- Compile, lint, and FL tests pass.

## Verification commands

```powershell
python -m compileall -q backend fl_server hospital_nodes xai_engine analytics database tests
ruff check backend fl_server hospital_nodes xai_engine analytics database tests
pytest tests/fl -q
```

The tests create temporary CSV files and do not require a running Flower server.
End-to-end multi-process Flower orchestration is exercised in the Docker and
integration testing phases.
