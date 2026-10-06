"""Unit tests for shared preprocessing, strategy config, and FL persistence."""

import json

import numpy as np
import pandas as pd
import pytest

from backend.app.models.enums import DatasetType
from fl_server.server.config import FederatedLearningConfig
from fl_server.server.dataset import apply_shared_preprocessing, load_healthcare_csv
from fl_server.server.persistence import FLPersistence, _unit_metric, to_sync_database_url
from fl_server.server.strategy import resolve_preprocessing
from hospital_nodes.client import build_client

# ---------------------------------------------------------------------------
# resolve_preprocessing
# ---------------------------------------------------------------------------


def test_resolve_preprocessing_defaults_to_identity() -> None:
    spec = resolve_preprocessing(None, 9)
    assert spec["type"] == "identity"
    assert len(spec["means"]) == 9


def test_resolve_preprocessing_keeps_valid_standardization() -> None:
    spec = {
        "type": "standardization",
        "means": [1.0] * 9,
        "scales": [2.0] * 9,
    }
    assert resolve_preprocessing(spec, 9) == spec


def test_resolve_preprocessing_rejects_wrong_dimension() -> None:
    spec = {"type": "standardization", "means": [1.0] * 4, "scales": [1.0] * 4}
    assert resolve_preprocessing(spec, 9)["type"] == "identity"


def test_resolve_preprocessing_rejects_unknown_type() -> None:
    assert resolve_preprocessing({"type": "quantile"}, 9)["type"] == "identity"


# ---------------------------------------------------------------------------
# apply_shared_preprocessing
# ---------------------------------------------------------------------------


def test_apply_shared_preprocessing_standardization_math() -> None:
    x = np.array([[1.0, 3.0], [5.0, 7.0]], dtype=np.float32)
    spec = {"type": "standardization", "means": [3.0, 5.0], "scales": [2.0, 2.0]}
    result = apply_shared_preprocessing(x, spec)
    np.testing.assert_allclose(result, [[-1.0, -1.0], [1.0, 1.0]], rtol=1e-6)


def test_apply_shared_preprocessing_identity_returns_input() -> None:
    x = np.array([[1.0, 2.0]], dtype=np.float32)
    assert apply_shared_preprocessing(x, {"type": "identity"}) is x
    assert apply_shared_preprocessing(x, None) is x


def test_apply_shared_preprocessing_rejects_dimension_mismatch() -> None:
    x = np.zeros((2, 9), dtype=np.float32)
    spec = {"type": "standardization", "means": [0.0] * 4, "scales": [1.0] * 4}
    with pytest.raises(ValueError, match="preprocessing expects 4 features"):
        apply_shared_preprocessing(x, spec)


def test_apply_shared_preprocessing_rejects_unknown_type() -> None:
    x = np.zeros((2, 9), dtype=np.float32)
    with pytest.raises(ValueError, match="Unsupported preprocessing type"):
        apply_shared_preprocessing(x, {"type": "pca"})


def test_apply_shared_preprocessing_handles_zero_scale() -> None:
    x = np.array([[1.0, 2.0]], dtype=np.float32)
    spec = {"type": "standardization", "means": [0.0, 0.0], "scales": [0.0, 1.0]}
    result = apply_shared_preprocessing(x, spec)
    np.testing.assert_allclose(result, [[1.0, 2.0]], rtol=1e-6)


# ---------------------------------------------------------------------------
# Client applies the shared spec from the round config
# ---------------------------------------------------------------------------


def _heart_csv(tmp_path, rows: int = 30):
    records = []
    for index in range(rows):
        records.append(
            {
                "age": 40 + index,
                "sex": index % 2,
                "cp": index % 4,
                "trestbps": 110 + index,
                "chol": 180 + index * 2,
                "fbs": index % 2,
                "thalach": 130 + index,
                "exang": (index + 1) % 2,
                "oldpeak": float(index % 5) / 10,
                "target": index % 2,
            }
        )
    path = tmp_path / "heart.csv"
    pd.DataFrame.from_records(records).to_csv(path, index=False)
    return path


def test_client_fit_applies_shared_preprocessing_from_config(tmp_path) -> None:
    path = _heart_csv(tmp_path)
    config = FederatedLearningConfig(epochs=1, batch_size=8, clients=1, rounds=1)
    client = build_client(
        node_id="hospital_test",
        data_path=path,
        dataset_type=DatasetType.HEART_DISEASE,
        config=config,
    )

    params = client.get_parameters({})
    spec = {"type": "standardization", "means": [50.0] * 9, "scales": [10.0] * 9}
    client.fit(params, {"preprocessing": json.dumps(spec)})

    assert client.dataset.applied_preprocessing == spec
    # Re-applied from raw arrays, not double-scaled
    raw = client.dataset.x_train_raw
    expected = ((raw - 50.0) / 10.0).astype(np.float32)
    np.testing.assert_allclose(client.dataset.x_train, expected, rtol=1e-5)

    # Second fit with the same spec must be a no-op (idempotent)
    before = client.dataset.x_train.copy()
    client.fit(params, {"preprocessing": json.dumps(spec)})
    np.testing.assert_array_equal(client.dataset.x_train, before)


def test_client_evaluate_applies_shared_preprocessing_from_config(tmp_path) -> None:
    path = _heart_csv(tmp_path)
    config = FederatedLearningConfig(epochs=1, batch_size=8, clients=1, rounds=1)
    client = build_client(
        node_id="hospital_test",
        data_path=path,
        dataset_type=DatasetType.HEART_DISEASE,
        config=config,
    )
    params = client.get_parameters({})
    spec = {"type": "standardization", "means": [50.0] * 9, "scales": [10.0] * 9}
    client.evaluate(params, {"preprocessing": json.dumps(spec)})
    assert client.dataset.applied_preprocessing == spec


# ---------------------------------------------------------------------------
# Strategy config carries the spec to clients
# ---------------------------------------------------------------------------


def test_fit_config_carries_preprocessing_json(tmp_path) -> None:
    from fl_server.server.app import create_strategy

    config = FederatedLearningConfig(
        rounds=1, clients=1, epochs=1, dataset_type=DatasetType.HEART_DISEASE,
        artifact_root=tmp_path,
    )
    strategy = create_strategy(config)
    fit_config = strategy.on_fit_config_fn(1)
    assert isinstance(fit_config["preprocessing"], str)
    spec = json.loads(fit_config["preprocessing"])
    assert spec["type"] in {"identity", "standardization"}
    assert len(spec["means"]) == 9


def test_load_healthcare_csv_keeps_raw_arrays(tmp_path) -> None:
    path = _heart_csv(tmp_path)
    dataset = load_healthcare_csv(path, dataset_type=DatasetType.HEART_DISEASE)
    assert dataset.x_train_raw is not None
    assert dataset.x_test_raw is not None
    assert dataset.x_train_raw.shape == dataset.x_train.shape


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def test_to_sync_database_url_rewrites_drivers() -> None:
    assert to_sync_database_url("postgresql+asyncpg://u:p@h/db").startswith(
        "postgresql+psycopg://"
    )
    assert to_sync_database_url("sqlite+aiosqlite:///:memory:") == "sqlite:///:memory:"


def test_unit_metric_enforces_db_constraints() -> None:
    assert _unit_metric({"accuracy": 0.9}, "accuracy") == 0.9
    assert _unit_metric({"accuracy": 1.5}, "accuracy") is None
    assert _unit_metric({"accuracy": -0.1}, "accuracy") is None
    assert _unit_metric({"loss": -1.0}, "loss") is None
    assert _unit_metric({"loss": 0.4}, "loss") == 0.4
    assert _unit_metric({"accuracy": True}, "accuracy") is None
    assert _unit_metric({}, "accuracy") is None
    assert _unit_metric({"accuracy": float("nan")}, "accuracy") is None


def test_persistence_is_noop_without_database_url() -> None:
    persistence = FLPersistence(
        None, dataset_type="heart_disease", total_clients=3
    )
    assert persistence.enabled is False
    assert persistence.load_active_model_path() is None
    assert persistence.activate_best() is None
    persistence.begin_run()
    persistence.register_round(round_number=1, metrics={"accuracy": 0.9})
