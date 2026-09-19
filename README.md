# FedPedia-XAI

FedPedia-XAI is a privacy-preserving healthcare prediction platform. Hospitals
train models locally, Flower coordinates federated rounds, FedAvg aggregates
model updates, and SHAP/LIME explain predictions without centralizing patient
records.

## Delivery status

Phase 1 established the monorepo architecture, package boundaries, PostgreSQL
schema, SQLAlchemy models, and Alembic migration workflow. Phase 2 adds the
FastAPI application shell, JWT authentication, refresh-session rotation, RBAC,
audit-aware user/hospital/patient APIs, and API documentation. Phase 3 adds the
Flower federated-learning runtime, explicit FedAvg/Weighted FedAvg aggregation,
three hospital clients, local PyTorch training, and checksummed global model
artifacts. Phase 4 adds the versioned prediction engine, model checksum
verification, doctor prediction APIs, and persisted prediction records. Phase 5
adds SHAP/LIME explainability, stored XAI artifacts, report metadata, and XAI
APIs. Later phases are intentionally gated by the project execution rules.

## Repository map

- `frontend/` — React/Vite clinical and operational dashboards.
- `backend/` — FastAPI APIs, authentication, domain services, and persistence.
- `fl_server/` — Flower strategy, aggregation, global model registry, and rounds.
- `hospital_nodes/` — three isolated hospital-client runtimes.
- `xai_engine/` — SHAP global explanations and LIME local explanations.
- `analytics/` — model comparison, metrics, and fairness analysis.
- `database/` — Alembic migrations and database operations.
- `docker/` — container and reverse-proxy infrastructure.
- `docs/` — architecture, database, deployment, user, and developer guidance.
- `tests/` — unit, API, ML, FL, and end-to-end integration tests.

## Phase 1 quick start

```powershell
cd FedPedia-XAI
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
```

PostgreSQL must be reachable using `DATABASE_URL`. No real credentials belong
in source control; `.env.example` contains development-only examples.

See [Architecture Guide](docs/architecture-guide.md) and
[Database Guide](docs/database-guide.md) for the Phase 1 design.
See [API Documentation](docs/api-documentation.md) for Phase 2 endpoints.
See [Federated Learning Guide](docs/federated-learning-guide.md) for Phase 3.
See [Prediction Engine Guide](docs/prediction-engine-guide.md) for Phase 4.
See [XAI Engine Guide](docs/xai-engine-guide.md) for Phase 5.
