# pyrefly: ignore [missing-import]
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import torch
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

import backend.app.models  # noqa: F401
from backend.app.core.config import Settings
from backend.app.database.base import Base
from backend.app.main import create_app
from backend.app.models.enums import DatasetType, ModelFramework, ModelSource
from backend.app.models.global_model import GlobalModel
from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.registry import ModelRegistry


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
    
    from backend.app.auth.rate_limit import InMemoryRateLimiter
    from backend.app.auth.sessions import InMemorySessionStore
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
    admin_refresh = resp.json()["refresh_token"]
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
        "sex": 1,
        "cp": 0,
        "bp": 120.0,
        "cholesterol": 230.0,
        "glucose": 100.0,
        "heart_rate": 150.0,
        "fbs": 0,
        "exang": 0,
        "oldpeak": 1.0
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
        f"/xai/predictions/{prediction_id}/reports",
        json={"regenerate": False, "background_size": 48},
        headers=doctor_headers
    )
    assert xai_resp.status_code == 201, f"Generate XAI report failed: {xai_resp.status_code} - {xai_resp.text}"

    # 8. Check Analytics using admin token (which has VIEW_METRICS permission)
    analytics_resp = await client.get("/analytics/fl/report", headers=admin_headers)
    assert analytics_resp.status_code == 200, f"Get analytics failed: {analytics_resp.status_code} - {analytics_resp.text}"
    assert "summary" in analytics_resp.json()

    # 9. Rounds list must be honest — no fabricated fallback rounds
    rounds_resp = await client.get("/analytics/fl/rounds", headers=admin_headers)
    assert rounds_resp.status_code == 200, f"Get rounds failed: {rounds_resp.status_code} - {rounds_resp.text}"
    assert rounds_resp.json() == []

    # 10. Fairness is computed from real stored predictions — caller sends only
    # the feature split, no group arrays, no rankings.  (The test model's
    # feature set is age/bp/cholesterol/glucose, so split on bp.)
    fairness_resp = await client.post(
        "/analytics/fairness",
        json={"feature_name": "bp", "privileged_group": "120"},
        headers=admin_headers,
    )
    assert fairness_resp.status_code == 200, (
        f"Fairness check failed: {fairness_resp.status_code} - {fairness_resp.text}"
    )
    fairness = fairness_resp.json()
    assert fairness["data_available"] is True
    assert len(fairness["group_analyses"]) == 1
    analysis = fairness["group_analyses"][0]
    assert analysis["feature_name"] == "bp"
    # No ground truth recorded → label-dependent metrics must be omitted
    assert analysis["ground_truth_available"] is False
    assert analysis["equalized_odds"] == {}
    assert "120" in analysis["group_metrics"]
    for metrics in analysis["group_metrics"].values():
        assert "positive_rate" in metrics
        assert "accuracy" not in metrics
        assert "labels" not in metrics

    # 11. Federated vs centralized comparison (admin, COMPARE_MODELS)
    resp = await client.get("/analytics/comparison", headers=admin_headers)
    assert resp.status_code == 200, f"Comparison failed: {resp.status_code} - {resp.text}"
    comparison = resp.json()
    assert {"federated", "centralized", "delta_table", "privacy_advantage"} <= comparison.keys()
    resp = await client.get(
        "/analytics/comparison?dataset_type=heart_disease", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text

    # 12. Node participation (admin, VIEW_METRICS)
    resp = await client.get("/analytics/fl/nodes", headers=admin_headers)
    assert resp.status_code == 200, f"Node analytics failed: {resp.status_code} - {resp.text}"
    assert set(resp.json()) == {"counts", "rates"}
    resp = await client.get("/analytics/fl/nodes?dataset_type=heart_disease", headers=admin_headers)
    assert resp.status_code == 200, resp.text

    # 13. Prediction statistics reflect the stored prediction + XAI report
    resp = await client.get("/analytics/predictions/stats", headers=admin_headers)
    assert resp.status_code == 200, f"Prediction stats failed: {resp.status_code} - {resp.text}"
    stats = resp.json()
    assert stats["total_predictions"] == 1
    assert stats["with_xai_report"] == 1
    assert stats["total_training_rounds"] == 0
    assert sum(stats["by_risk_level"].values()) == 1
    resp = await client.get(
        "/analytics/predictions/stats?dataset_type=heart_disease", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text

    # 14. XAI report retrieval (doctor, VIEW_EXPLANATIONS)
    xai_id = xai_resp.json()["id"]
    resp = await client.get(f"/xai/reports/{xai_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Get XAI report failed: {resp.status_code} - {resp.text}"
    assert resp.json()["id"] == xai_id
    assert resp.json()["top_shap_features"] is not None
    resp = await client.get(f"/xai/predictions/{prediction_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Get XAI by prediction failed: {resp.status_code} - {resp.text}"
    assert resp.json()["prediction_id"] == prediction_id

    # 15. Predictions list + detail (doctor)
    resp = await client.get("/predictions", headers=doctor_headers)
    assert resp.status_code == 200, f"List predictions failed: {resp.status_code} - {resp.text}"
    page = resp.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == prediction_id
    resp = await client.get(f"/predictions/{prediction_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Get prediction failed: {resp.status_code} - {resp.text}"
    assert resp.json()["id"] == prediction_id

    # 16. Preview runs the active model without persisting (doctor)
    resp = await client.post(
        "/predictions/preview",
        json={
            "features": {
                "age": 55,
                "sex": 1,
                "cp": 2,
                "bp": 130.0,
                "cholesterol": 240.0,
                "glucose": 110.0,
                "heart_rate": 150.0,
                "fbs": 1,
                "exang": 0,
                "oldpeak": 1.5,
            },
            "dataset_type": "heart_disease",
            "model_source": "federated",
        },
        headers=doctor_headers,
    )
    assert resp.status_code == 200, f"Preview failed: {resp.status_code} - {resp.text}"
    preview = resp.json()
    assert 0.0 <= preview["probability"] <= 1.0
    assert preview["risk_level"] in {"low", "moderate", "high"}

    # 17. PDF clinical report (doctor, DOWNLOAD_REPORTS)
    resp = await client.get(f"/reports/predictions/{prediction_id}/pdf", headers=doctor_headers)
    assert resp.status_code == 200, f"PDF report failed: {resp.status_code} - {resp.text}"
    media_type = resp.headers["content-type"]
    assert media_type in {"application/pdf", "text/html"}
    if media_type == "application/pdf":
        assert resp.content.startswith(b"%PDF")
    else:
        assert "FedPedia-XAI" in resp.text

    # 18. Predictions CSV export (doctor, DOWNLOAD_REPORTS)
    resp = await client.get("/reports/predictions/csv", headers=doctor_headers)
    assert resp.status_code == 200, f"CSV export failed: {resp.status_code} - {resp.text}"
    assert resp.headers["content-type"].startswith("text/csv")
    assert prediction_id in resp.text

    # 19. Fairness CSV export from the real analysis payload (admin)
    resp = await client.post("/reports/fairness/csv", json=fairness, headers=admin_headers)
    assert resp.status_code == 200, f"Fairness CSV failed: {resp.status_code} - {resp.text}"
    assert "feature_name" in resp.text

    # 20. Training monitor: rounds list is honestly empty (admin, VIEW_METRICS)
    resp = await client.get("/training/rounds", headers=admin_headers)
    assert resp.status_code == 200, f"Training rounds failed: {resp.status_code} - {resp.text}"
    assert resp.json() == {"total": 0, "offset": 0, "limit": 100, "rounds": []}
    resp = await client.get("/training/rounds?dataset_type=heart_disease", headers=admin_headers)
    assert resp.status_code == 200, resp.text

    # 21. Unknown round 404s on detail and advisory cancel
    missing_round = str(uuid.uuid4())
    resp = await client.get(f"/training/rounds/{missing_round}", headers=admin_headers)
    assert resp.status_code == 404, f"Missing round should 404: {resp.status_code} - {resp.text}"
    resp = await client.post(f"/training/rounds/{missing_round}/cancel", headers=admin_headers)
    assert resp.status_code == 404, f"Cancel missing round should 404: {resp.status_code}"

    # 22. Global model registry endpoints (admin)
    resp = await client.get("/training/models", headers=admin_headers)
    assert resp.status_code == 200, f"Models list failed: {resp.status_code} - {resp.text}"
    models = resp.json()
    assert len(models) == 1
    assert models[0]["is_active"] is True
    assert models[0]["input_dim"] == 4
    resp = await client.get("/training/models?dataset_type=heart_disease", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get("/training/models/active", headers=admin_headers)
    assert resp.status_code == 200, f"Active model failed: {resp.status_code} - {resp.text}"
    active = resp.json()
    assert active["id"] == models[0]["id"]
    assert active["feature_names"] == ["age", "bp", "cholesterol", "glucose"]

    # 23. Hospital node status (admin, MONITOR_HOSPITAL_NODE)
    resp = await client.get("/training/nodes", headers=admin_headers)
    assert resp.status_code == 200, f"Training nodes failed: {resp.status_code} - {resp.text}"
    nodes = resp.json()
    assert len(nodes) == 1
    assert nodes[0]["node_id"] == "hospital-node-1"

    # 24. Hospitals list / detail / update (admin)
    resp = await client.get("/hospitals", headers=admin_headers)
    assert resp.status_code == 200, f"Hospitals list failed: {resp.status_code} - {resp.text}"
    assert resp.json()["total"] == 1
    resp = await client.get(f"/hospitals/{hospital_id}", headers=admin_headers)
    assert resp.status_code == 200, f"Hospital detail failed: {resp.status_code} - {resp.text}"
    resp = await client.patch(
        f"/hospitals/{hospital_id}", json={"status": "online"}, headers=admin_headers
    )
    assert resp.status_code == 200, f"Hospital patch failed: {resp.status_code} - {resp.text}"
    assert resp.json()["status"] == "online"

    # 25. Patients list / detail / update (doctor)
    resp = await client.get("/patients", headers=doctor_headers)
    assert resp.status_code == 200, f"Patients list failed: {resp.status_code} - {resp.text}"
    assert resp.json()["total"] == 1
    resp = await client.get(f"/patients/{patient_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Patient detail failed: {resp.status_code} - {resp.text}"
    resp = await client.patch(
        f"/patients/{patient_id}", json={"bp": 125.0}, headers=doctor_headers
    )
    assert resp.status_code == 200, f"Patient patch failed: {resp.status_code} - {resp.text}"
    assert resp.json()["bp"] == 125.0

    # 26. A second patient covers the create + delete paths (doctor)
    resp = await client.post(
        "/patients", json={"age": 60, "sex": 0, "bp": 118.0}, headers=doctor_headers
    )
    assert resp.status_code == 201, f"Create patient 2 failed: {resp.status_code} - {resp.text}"
    patient2_id = resp.json()["id"]
    resp = await client.delete(f"/patients/{patient2_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Delete patient 2 failed: {resp.status_code} - {resp.text}"

    # 27. Second prediction covers the delete path without touching the XAI report
    resp = await client.post(
        "/predictions",
        json={
            "patient_id": patient_id,
            "dataset_type": "heart_disease",
            "model_source": "federated",
        },
        headers=doctor_headers,
    )
    assert resp.status_code == 201, f"Create prediction 2 failed: {resp.status_code} - {resp.text}"
    second_prediction_id = resp.json()["id"]
    resp = await client.delete(f"/predictions/{second_prediction_id}", headers=doctor_headers)
    assert resp.status_code == 200, f"Delete prediction failed: {resp.status_code} - {resp.text}"
    resp = await client.get(f"/predictions/{second_prediction_id}", headers=doctor_headers)
    assert resp.status_code == 404, f"Deleted prediction should 404: {resp.status_code}"

    # 28. User management (admin): list / create / read / update / delete
    resp = await client.post(
        "/users",
        json={
            "email": "researcher@test.com",
            "password": "ResearchPass123!",
            "name": "Test Researcher",
            "role": "researcher",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, f"Create user failed: {resp.status_code} - {resp.text}"
    researcher_id = resp.json()["id"]
    resp = await client.get("/users", headers=admin_headers)
    assert resp.status_code == 200, f"Users list failed: {resp.status_code} - {resp.text}"
    assert resp.json()["total"] == 3
    resp = await client.get(f"/users/{researcher_id}", headers=admin_headers)
    assert resp.status_code == 200, f"User detail failed: {resp.status_code} - {resp.text}"
    resp = await client.patch(
        f"/users/{researcher_id}", json={"name": "Renamed Researcher"}, headers=admin_headers
    )
    assert resp.status_code == 200, f"User patch failed: {resp.status_code} - {resp.text}"
    assert resp.json()["name"] == "Renamed Researcher"
    resp = await client.get("/users/me", headers=admin_headers)
    assert resp.status_code == 200, f"Own profile failed: {resp.status_code} - {resp.text}"
    assert resp.json()["email"] == "admin@test.com"
    resp = await client.delete(f"/users/{researcher_id}", headers=admin_headers)
    assert resp.status_code == 200, f"Deactivate user failed: {resp.status_code} - {resp.text}"
    # Deactivation is a soft delete: the profile remains readable, marked inactive.
    resp = await client.get(f"/users/{researcher_id}", headers=admin_headers)
    assert resp.status_code == 200, f"Deactivated user should still read: {resp.status_code}"
    assert resp.json()["is_active"] is False

    # 29. Health probe (unauthenticated)
    resp = await client.get("/health")
    assert resp.status_code == 200, f"Health failed: {resp.status_code} - {resp.text}"
    health = resp.json()
    assert health["database"] == "up"
    assert health["status"] == "ok"

    # 30. Refresh rotation issues a working access token, logout revokes it (admin)
    resp = await client.post("/auth/refresh", json={"refresh_token": admin_refresh})
    assert resp.status_code == 200, f"Refresh failed: {resp.status_code} - {resp.text}"
    refreshed_token = resp.json()["access_token"]
    refreshed_headers = {"Authorization": f"Bearer {refreshed_token}"}
    resp = await client.get("/auth/me", headers=refreshed_headers)
    assert resp.status_code == 200, f"Me with refreshed token failed: {resp.status_code}"
    assert resp.json()["email"] == "admin@test.com"
    resp = await client.post("/auth/logout", headers=refreshed_headers)
    assert resp.status_code == 200, f"Logout failed: {resp.status_code} - {resp.text}"
    resp = await client.get("/auth/me", headers=refreshed_headers)
    assert resp.status_code == 401, f"Revoked token should 401: {resp.status_code}"

    # 31. Doctor changes password, logs in with it, then logs out (doctor)
    resp = await client.patch(
        "/users/me/password",
        json={
            "current_password": "DoctorPassword123!",
            "new_password": "NewDoctorPass456!",
        },
        headers=doctor_headers,
    )
    assert resp.status_code == 200, f"Password change failed: {resp.status_code} - {resp.text}"
    resp = await client.post(
        "/auth/login",
        json={"email": "doctor@test.com", "password": "NewDoctorPass456!"},
    )
    assert resp.status_code == 200, f"Login with new password failed: {resp.status_code}"
    new_doctor_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = await client.get("/auth/me", headers=new_doctor_headers)
    assert resp.status_code == 200, f"Me after password change failed: {resp.status_code}"
    resp = await client.post("/auth/logout", headers=new_doctor_headers)
    assert resp.status_code == 200, f"Doctor logout failed: {resp.status_code} - {resp.text}"
    resp = await client.get("/auth/me", headers=new_doctor_headers)
    assert resp.status_code == 401, f"Doctor revoked token should 401: {resp.status_code}"
