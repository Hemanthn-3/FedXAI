import json

import numpy as np
import torch

from backend.app.models.enums import DatasetType
from fl_server.server.aggregation import (
    ClientUpdate,
    aggregate_client_metrics,
    aggregate_fedavg,
    aggregate_weighted_fedavg,
)
from fl_server.server.registry import ModelRegistry


def _updates() -> list[ClientUpdate]:
    return [
        ClientUpdate(
            node_id="hospital_1",
            parameters=[np.array([1.0, 3.0], dtype=np.float32)],
            num_examples=10,
            metrics={"loss": 0.4, "accuracy": 0.8},
        ),
        ClientUpdate(
            node_id="hospital_2",
            parameters=[np.array([5.0, 7.0], dtype=np.float32)],
            num_examples=30,
            metrics={"loss": 0.2, "accuracy": 0.9},
        ),
    ]


def test_fedavg_averages_each_hospital_equally() -> None:
    result = aggregate_fedavg(_updates())

    np.testing.assert_allclose(result[0], np.array([3.0, 5.0], dtype=np.float32))


def test_weighted_fedavg_uses_training_examples() -> None:
    result = aggregate_weighted_fedavg(_updates())

    np.testing.assert_allclose(result[0], np.array([4.0, 6.0], dtype=np.float32))


def test_aggregate_client_metrics_are_example_weighted() -> None:
    metrics = aggregate_client_metrics(_updates())

    assert metrics["total_examples"] == 40
    assert metrics["participating_clients"] == 2
    assert metrics["accuracy"] == 0.875


def test_model_registry_saves_checksummed_artifact_and_round_history(tmp_path) -> None:
    from fl_server.server.model import create_model, get_model_parameters

    registry = ModelRegistry(tmp_path)
    parameters = get_model_parameters(create_model(input_dim=2))
    artifact = registry.save_global_model(
        parameters=parameters,
        input_dim=2,
        dataset_type=DatasetType.HEART_DISEASE,
        round_number=1,
        metrics={"accuracy": 0.9},
        feature_names=("feature_1", "feature_2"),
    )
    history = registry.record_round_metrics(
        round_number=1,
        dataset_type=DatasetType.HEART_DISEASE,
        aggregation_strategy="fedavg",
        metrics={"accuracy": 0.9},
        artifact=artifact,
    )

    assert artifact.path.exists()
    assert len(artifact.checksum_sha256) == 64
    payload = torch.load(artifact.path, map_location="cpu")
    assert payload["input_dim"] == 2
    line = history.read_text(encoding="utf-8").strip()
    assert json.loads(line)["artifact"]["checksum_sha256"] == artifact.checksum_sha256
