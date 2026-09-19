# Phase 2 Verification

## Acceptance criteria

- FastAPI app imports and generates OpenAPI without connecting to PostgreSQL.
- `/auth/register`, `/auth/login`, `/auth/refresh`, and `/auth/me` exist.
- Access tokens and refresh tokens are signed, typed, expiring JWTs.
- Refresh-token IDs are hashed in session storage and rotate on refresh.
- Password hashing verifies valid passwords and rejects invalid passwords.
- RBAC exposes the required role permissions.
- User, hospital, and patient APIs enforce authentication and role scope.
- Sensitive mutations create audit-log records.
- Linting, syntax compilation, unit tests, and OpenAPI checks pass.

## Verification commands

```powershell
python -m compileall -q backend fl_server hospital_nodes xai_engine analytics database tests
ruff check backend fl_server hospital_nodes xai_engine analytics database tests
pytest tests/unit tests/api
python -c "from backend.app.main import create_app; app=create_app(); print(len(app.openapi()['paths']))"
```

The endpoint tests use memory-backed sessions and rate limiting, so they do not
require Redis. Full database integration still requires PostgreSQL and will be
expanded in Phase 7.
