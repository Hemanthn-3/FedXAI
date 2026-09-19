from backend.app.core.config import Settings
from backend.app.main import create_app


def test_openapi_contains_phase_2_routes() -> None:
    app = create_app(
        Settings(
            session_backend="memory",
            rate_limit_backend="memory",
            database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
        )
    )
    schema = app.openapi()
    paths = schema["paths"]

    assert "/api/v1/auth/register" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/hospitals" in paths
    assert "/api/v1/patients" in paths
    assert "/api/v1/predictions" in paths
    assert "/api/v1/predictions/preview" in paths
    assert "/api/v1/xai/reports/{prediction_id}" in paths
    assert "/api/v1/xai/predictions/{prediction_id}" in paths
    assert "/api/v1/health" in paths
