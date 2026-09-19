# Phase 1 Verification

## Acceptance criteria

- The required monorepo directories exist.
- Python packages import from the repository root.
- Configuration validates environment values.
- All eight required SQLAlchemy entities are registered in shared metadata.
- Model relationships and database constraints are internally consistent.
- The initial Alembic migration supports upgrade and downgrade.
- Architecture and database decisions are documented.

## Verification commands

```powershell
python -m compileall backend fl_server hospital_nodes xai_engine analytics database
python -m pip install -e ".[dev]"
python -c "from backend.app.models import *; from backend.app.database.base import Base; print(sorted(Base.metadata.tables))"
ruff check backend fl_server hospital_nodes xai_engine analytics database
alembic upgrade head
alembic check
```

The final two Alembic commands require a reachable PostgreSQL instance using
`DATABASE_URL`. Schema compilation and metadata registration can be verified
without a running database.
