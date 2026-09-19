# FedPedia-XAI Architecture Guide

## 1. Architectural goals

FedPedia-XAI separates clinical data ownership from collaborative model
training. Raw hospital datasets remain inside hospital-node trust boundaries.
The federated server receives model parameters and aggregate metrics only.
Prediction records retain the model version and input snapshot needed for
clinical traceability, while SHAP and LIME artifacts are generated outside the
training path.

The platform is organized as a modular monorepo so each runtime can be tested,
containerized, deployed, and scaled independently.

## 2. System context

```text
Doctors ───────┐
Hospital Admins├──> React UI ──> FastAPI ──> PostgreSQL / Redis
System Admins ─┤                     │
Researchers ───┘                     ├──> Prediction + XAI + Reports
                                     │
Hospital 1 client ──local weights────┤
Hospital 2 client ──local weights────┼──> Flower server ──> Global model
Hospital 3 client ──local weights────┘
```

### Trust boundaries

1. Each hospital node owns its raw healthcare dataset and fitted preprocessing
   state. Raw rows do not cross the node boundary.
2. The Flower server accepts model updates from registered hospital nodes and
   applies FedAvg or Weighted FedAvg.
3. The backend owns identity, authorization, operational metadata, predictions,
   reports, and audit events.
4. Model and explanation files live in an artifact store; PostgreSQL stores
   immutable paths, checksums, versions, status, and provenance.
5. Redis is reserved for short-lived sessions, rate limits, notification work,
   and live training telemetry. PostgreSQL remains the system of record.

## 3. Module boundaries

| Module | Responsibility | Authoritative data |
|---|---|---|
| Authentication Service | Access/refresh tokens, password verification, sessions | Users, sessions |
| User Management | Role assignment and hospital membership | Users |
| Hospital Management | Node registration, health, and status | Hospitals |
| Dataset Manager | Schema validation and local dataset lifecycle | Hospital-local files |
| Preprocessing Engine | Reusable fitted transformations | Hospital-local artifacts |
| Federated Learning Engine | Client orchestration and local training contract | Round configuration |
| Aggregation Server | FedAvg/Weighted FedAvg and model publication | Training rounds, model registry |
| Prediction Engine | Versioned inference and risk classification | Predictions |
| XAI Engine | SHAP global and LIME local explanations | XAI reports and plots |
| Analytics Engine | FL/centralized comparison, fairness, performance | Derived metrics |
| Monitoring Dashboard | Live node and round observability | Redis telemetry, PostgreSQL history |
| Report Generator | Clinical PDF and CSV exports | Generated reports |
| Audit Logging | Append-only security and domain events | Audit logs |
| Notification Service | Training, node, and report notifications | Delivery state |
| Deployment Infrastructure | Network, secrets, persistence, health checks | Environment configuration |

## 4. Runtime data flow

### Federated training

1. A system or hospital administrator starts an authorized training run.
2. The server selects healthy registered clients and sends the current global
   model plus round configuration.
3. Each client loads and preprocesses only its local dataset.
4. Each client trains for the configured local epochs and evaluates locally.
5. Clients return weights, sample counts, and non-identifying metrics.
6. The server rejects malformed or unregistered updates and aggregates accepted
   updates with FedAvg or Weighted FedAvg.
7. The resulting model is checksummed, versioned, stored, and associated with a
   completed training-round record.
8. The model is redistributed for the next round until the run completes.

### Prediction and explanation

1. A doctor selects or creates a patient and submits validated features.
2. The prediction service resolves the active model for the dataset type.
3. The exact input snapshot, model identity, probability, binary class, and risk
   level are persisted.
4. The XAI service produces SHAP and LIME artifacts tied to that prediction.
5. The report service combines prediction provenance, confidence, explanations,
   and doctor notes into PDF/CSV outputs.
6. Security-sensitive actions produce append-only audit events.

## 5. Repository structure

```text
FedPedia-XAI/
├── analytics/
├── backend/
│   └── app/
│       ├── api/
│       ├── auth/
│       ├── core/
│       ├── database/
│       ├── models/
│       ├── services/
│       └── utils/
├── database/
│   └── migrations/
│       └── versions/
├── docker/
├── docs/
├── fl_server/
│   └── server/
├── frontend/
│   └── src/
├── hospital_nodes/
│   ├── node_1/
│   ├── node_2/
│   └── node_3/
├── tests/
│   ├── api/
│   ├── fl/
│   ├── integration/
│   ├── ml/
│   └── unit/
└── xai_engine/
    ├── lime/
    └── shap/
```

## 6. Key architecture decisions

### UUID primary keys

UUIDs avoid exposing sequential record counts and allow independent services to
create identifiers without a central sequence. Human-facing model versions and
hospital node IDs remain separately indexed.

### PostgreSQL as the system of record

Clinical and training provenance needs transactions, constraints, referential
integrity, and durable auditability. JSONB is limited to naturally variable
payloads such as feature snapshots and metric maps; core searchable fields stay
relational.

### Asynchronous database access

The FastAPI data layer uses SQLAlchemy's async engine with `asyncpg`. Alembic
uses a synchronous `psycopg` connection because migrations are operational,
short-lived processes rather than request-path work.

### Artifact registry instead of database blobs

Global models and XAI plots are stored as files or object-storage objects.
`global_models` records their version, path, framework, source, metrics, and
SHA-256 checksum. This keeps database backups manageable while preserving
tamper-evident provenance.

### One active model per task and source

A partial unique PostgreSQL index permits only one active model for each
dataset/source pair. Model activation therefore becomes an atomic database
operation and avoids ambiguous inference.

### Append-only audit logging

The initial migration installs a database trigger that rejects updates and
deletes on `audit_logs`. Application permissions alone are not considered a
sufficient immutability boundary.

### Privacy-extension seams

Differential privacy belongs in the hospital client before an update leaves the
node. Secure aggregation belongs in the client/server update protocol.
Homomorphic encryption belongs in a replaceable aggregation transport and
strategy implementation. These seams allow future privacy controls without
changing prediction, XAI, or user-facing APIs.

## 7. Scalability and failure behavior

- Stateless API replicas share PostgreSQL and Redis.
- Hospital nodes reconnect independently; one unavailable node does not expose
  its data or corrupt completed rounds.
- A round records intended and actual participation so partial participation is
  measurable.
- Model publication is versioned and checksum-verified before activation.
- XAI and report generation can run asynchronously without delaying inference.
- Historical models remain addressable for prediction reproducibility.

## 8. Security baseline

- Hospital-scoped roles require a hospital foreign key.
- System-wide roles may operate without hospital membership.
- Patient deletion is restricted when predictions require retained provenance.
- Model deletion is decoupled from predictions and rounds through nullable
  references, allowing retention policies without destroying clinical history.
- Secrets are environment-provided and excluded from source control.
- Network encryption, JWT/RBAC, rate limiting, and session enforcement are
  implemented in their designated delivery phases.
