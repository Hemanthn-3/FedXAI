# FedPedia-XAI API Documentation

## Base URL

The Phase 2 API is exposed under:

```text
/api/v1
```

Interactive OpenAPI documentation is available at:

```text
/api/v1/docs
```

## Authentication model

FedPedia-XAI uses a two-token model:

- Access token: short-lived JWT used in the `Authorization: Bearer <token>`
  header.
- Refresh token: long-lived JWT tied to a server-side session. Refresh tokens
  rotate on every use. If an old refresh token is reused, the session is
  revoked.

Passwords are hashed with Argon2 through `pwdlib`. Refresh-token identifiers
are hashed before session storage. Redis is the production session store;
in-memory storage is available for tests and single-process development.

## Roles and permissions

| Role | Main permissions |
|---|---|
| Doctor | View patients, create predictions, view explanations, download reports |
| Hospital Admin | Upload datasets, start training, monitor hospital node, view metrics |
| System Admin | Manage hospitals, manage users, control FL rounds, monitor aggregation |
| Researcher | Compare FL vs centralized, analyze fairness, analyze performance |

Doctor and hospital-admin users must belong to a hospital. System-admin and
researcher users are platform-scoped.

## Endpoints

### Health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | No | Liveness probe |

### Authentication

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | No | Register a doctor/researcher, or bootstrap the first system admin |
| POST | `/auth/login` | No | Login and create a refresh session |
| POST | `/auth/refresh` | No | Rotate refresh token and issue a new access token |
| POST | `/auth/logout` | Yes | Revoke current session |
| GET | `/auth/me` | Yes | Read current authenticated user |

Bootstrap rule: the first user may register as `system_admin` when
`BOOTSTRAP_ADMIN_ENABLED=true`. After any user exists, system administrators
must create privileged users through `/users`.

### Users

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/users` | System Admin | List users |
| POST | `/users` | System Admin | Create users in any role |
| GET | `/users/me` | Any user | Read own profile |
| PATCH | `/users/me/password` | Any user | Change own password |
| GET | `/users/{user_id}` | Self or System Admin | Read user profile |
| PATCH | `/users/{user_id}` | System Admin | Update role, hospital, active status, or profile |
| DELETE | `/users/{user_id}` | System Admin | Deactivate user |

### Hospitals

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/hospitals` | Any user | List all hospitals for system roles, or own hospital |
| POST | `/hospitals` | System Admin | Register hospital and node ID |
| GET | `/hospitals/{hospital_id}` | Scoped | Read hospital |
| PATCH | `/hospitals/{hospital_id}` | System Admin | Update hospital metadata/status |

### Patients

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/patients` | Doctor, Hospital Admin, System Admin | List scoped patients |
| POST | `/patients` | Doctor, Hospital Admin, System Admin | Create patient |
| GET | `/patients/{patient_id}` | Scoped | Read patient |
| PATCH | `/patients/{patient_id}` | Scoped | Update patient |

Researchers cannot read identifiable patient records in Phase 2. They receive
performance and fairness analytics in later phases.

### Predictions

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/predictions/preview` | Doctor | Run the active model against supplied features without persistence |
| POST | `/predictions` | Doctor | Create and persist a patient prediction |
| GET | `/predictions` | Doctor, System Admin | List persisted predictions |
| GET | `/predictions/{prediction_id}` | Scoped | Read persisted prediction |

Example preview request:

```json
{
  "dataset_type": "heart_disease",
  "model_source": "federated",
  "features": {
    "age": 52,
    "bp": 130,
    "cholesterol": 240,
    "glucose": 115
  }
}
```

Example response:

```json
{
  "prediction": 1,
  "risk": "High",
  "probability": 0.92,
  "risk_level": "high",
  "model_version": "federated-heart_disease-r0020-20260618120000",
  "dataset_type": "heart_disease",
  "model_source": "federated",
  "feature_names": ["age", "bp", "cholesterol", "glucose"],
  "warnings": []
}
```

Persisted predictions must reference a patient. If no explicit `features`
object is provided, the service uses canonical patient fields such as `age`,
`bp`, `cholesterol`, and `glucose`. If the active model requires additional
features, the API returns a validation error listing missing features.

### Explainability

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/xai/reports/{prediction_id}` | Doctor | Generate SHAP and LIME artifacts |
| GET | `/xai/reports/{report_id}` | Doctor | Read an XAI report by report ID |
| GET | `/xai/predictions/{prediction_id}` | Doctor | Read an XAI report by prediction ID |

Generated reports include SHAP summary, waterfall, bar, force, feature ranking,
LIME local explanation, feature contributions, and top influencing features.

## Error format

All handled errors return a consistent envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [],
    "request_id": "..."
  }
}
```

## Audit logging

The API records audit events for registration, login, refresh, logout, user
management, hospital management, password changes, and patient mutations.
`audit_logs` is append-only at the database layer.
