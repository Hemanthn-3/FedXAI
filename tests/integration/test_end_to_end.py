import asyncio
# pyrefly: ignore [missing-import]
import pytest
from httpx import ASGITransport, AsyncClient
from typing import AsyncGenerator
import tempfile
import torch
from pathlib import Path

from backend.app.main import create_app
from backend.app.core.config import Settings
from backend.app.database.base import Base
import backend.app.models  # noqa: F401
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, INET

from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.registry import ModelRegistry
from backend.app.models.enums import DatasetType, ModelFramework, ModelSource
from backend.app.models.global_model import GlobalModel

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(INET, "sqlite")
def compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def app_and_client() -> AsyncGenerator[tuple, None]:
    # Set up engine and create tables
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    # Save a mock global model artifact
    temp_dir = tempfile.TemporaryDirectory()
    model = create_model(input_dim=4)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.network[-1].bias.fill_(2.0)
    registry = ModelRegistry(Path(temp_dir.name))
    artifact = registry.save_global_model(
        parameters=get_model_parameters(model),
        input_dim=4,
        dataset_type=DatasetType.HEART_DISEASE,
        round_number=1,
        metrics={"accuracy": 1.0},
        feature_names=("age", "bp", "cholesterol", "glucose"),
    )

    async with session_maker() as session:
        global_model = GlobalModel(
            version="1.0.0",
            path=str(artifact.path),
            checksum_sha256=artifact.checksum_sha256,
            dataset_type=DatasetType.HEART_DISEASE,
            framework=ModelFramework.PYTORCH,
            source=ModelSource.FEDERATED,
            metrics={"accuracy": 1.0},
            is_active=True,
        )
        session.add(global_model)
        await session.commit()

    app = create_app(
        Settings(
            database_url=TEST_DATABASE_URL,
            session_backend="memory",
            rate_limit_backend="memory",
            jwt_secret_key="test_secret_key_which_is_extremely_long_and_secure_for_testing_purposes",
            jwt_refresh_secret_key="test_refresh_secret_key_which_is_extremely_long_and_secure_for_testing_purposes",
        )
    )
    
    from backend.app.auth.sessions import InMemorySessionStore
    from backend.app.auth.rate_limit import InMemoryRateLimiter
    app.state.session_store = InMemorySessionStore()
    app.state.rate_limiter = InMemoryRateLimiter()
    
    # Dependency override
    from backend.app.database.session import get_db_session
    async def override_get_db_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            
    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost/api/v1") as client:
        yield app, client

    await app.state.session_store.close()
    await app.state.rate_limiter.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    temp_dir.cleanup()


@pytest.mark.asyncio
async def test_full_system_flow(app_and_client: tuple) -> None:
    app, client = app_and_client

    # 1. Register an admin user
    resp = await client.post("/auth/register", json={
        "email": "admin@test.com",
        "password": "StrongPassword123!",
        "name": "Test Admin",
        "role": "system_admin"
    })
    assert resp.status_code == 201, f"Register failed: {resp.status_code} - {resp.text}"
    
    # 2. Login
    resp = await client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "StrongPassword123!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.status_code} - {resp.text}"
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Create a Hospital using system_admin token
    resp = await client.post("/hospitals", json={
        "name": "General Test Hospital",
        "location": "US-East",
        "node_id": "hospital-node-1"
    }, headers=admin_headers)
    assert resp.status_code == 201, f"Create hospital failed: {resp.status_code} - {resp.text}"
    hospital_id = resp.json()["id"]

    # 4. Register a Doctor user attached to the hospital
    resp = await client.post("/auth/register", json={
        "email": "doctor@test.com",
        "password": "DoctorPassword123!",
        "name": "Test Doctor",
        "role": "doctor",
        "hospital_id": hospital_id
    })
    assert resp.status_code == 201, f"Doctor register failed: {resp.status_code} - {resp.text}"
    doctor_token = resp.json()["access_token"]
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

    # 5. Create a Patient using doctor token
    resp = await client.post("/patients", json={
        "hospital_id": hospital_id,
        "age": 45,
        "bp": 120.0,
        "cholesterol": 230.0,
        "glucose": 100.0
    }, headers=doctor_headers)
    assert resp.status_code == 201, f"Create patient failed: {resp.status_code} - {resp.text}"
    patient_id = resp.json()["id"]

    # 6. Submit prediction using doctor token
    resp = await client.post("/predictions", json={
        "patient_id": patient_id,
        "dataset_type": "heart_disease",
        "model_source": "federated"
    }, headers=doctor_headers)
    assert resp.status_code == 201, f"Create prediction failed: {resp.status_code} - {resp.text}"
    prediction_id = resp.json()["id"]
    
    # 7. Generate XAI Report using doctor token
    xai_resp = await client.post(
        f"/xai/reports/{prediction_id}",
        json={"regenerate": False, "background_size": 48},
        headers=doctor_headers
    )
    assert xai_resp.status_code == 201, f"Generate XAI report failed: {xai_resp.status_code} - {xai_resp.text}"

    # 8. Check Analytics using admin token (which has VIEW_METRICS permission)
    analytics_resp = await client.get("/analytics/fl/report", headers=admin_headers)
    assert analytics_resp.status_code == 200, f"Get analytics failed: {analytics_resp.status_code} - {analytics_resp.text}"
    assert "summary" in analytics_resp.json()
