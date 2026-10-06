# FedPedia-XAI

[![CI](https://github.com/Hemanthn-3/FedXAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Hemanthn-3/FedXAI/actions/workflows/ci.yml)

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

## Federated lifecycle

The Flower network implements the seven-step lifecycle end to end:

1. The seeder trains a bootstrap global model and registers it before any
   server starts, so round 1 always has initial parameters.
2. The FL server distributes the active global model to the three hospital
   nodes.
3. Each node trains locally on its own CSV using shared preprocessing.
4. Doctors run predictions with SHAP/LIME explanations (kept doctor-facing,
   outside the FL loop).
5. Nodes return weight updates; FedAvg aggregates them in `aggregate_fit`.
6. Every aggregated round is persisted to `training_rounds` and registered as
   a checksummed `global_models` artifact.
7. After the final round the best-scoring model is activated for serving.

`fl_server/server/persistence.py` bridges Flower to Postgres and fails open
when no database is configured.

## Quick start (full stack)

```powershell
Copy-Item .env.example .env
# Set JWT_SECRET_KEY, JWT_REFRESH_SECRET_KEY, PATIENT_FIELD_ENCRYPTION_KEY in .env
docker compose up -d --build
```

The one-shot `seeder` service runs migrations, seeds hospitals and users,
trains the bootstrap model, and only then starts `backend`, `fl_server`, and
the hospital nodes. After 20 federated rounds the FL server exits cleanly.

Seeded logins:

| Role           | Email                | Password     |
| -------------- | -------------------- | ------------ |
| system_admin   | sysadmin@fedpedia.com | SysAdmin@2025 |
| hospital_admin | admin@fedpedia.com   | FedAdmin@2025 |
| doctor         | doctor.h1@fedpedia.com | DrNode1@2025 |
| doctor         | doctor.h2@fedpedia.com | DrNode2@2025 |
| doctor         | doctor.h3@fedpedia.com | DrNode3@2025 |

Frontend: `http://localhost` · Health: `http://localhost:8000/api/v1/health`

## Quality gates

```powershell
ruff check .                      # lint
pytest --cov -q                   # 107 tests, enforced 85% coverage gate
cd frontend; npm run lint; npm run test; npm run build
```

`.github/workflows/ci.yml` runs the same gates on every push and pull request.

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
