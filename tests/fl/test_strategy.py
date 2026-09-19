from types import SimpleNamespace

from flwr.common import Code, FitRes, Status, ndarrays_to_parameters, parameters_to_ndarrays

from backend.app.models.enums import DatasetType
from fl_server.server.app import create_strategy
from fl_server.server.config import FederatedLearningConfig


def test_strategy_aggregates_flower_fit_results_and_saves_artifact(tmp_path) -> None:
    config = FederatedLearningConfig(
        rounds=1,
        clients=2,
        epochs=1,
        batch_size=4,
        dataset_type=DatasetType.HEART_DISEASE,
        artifact_root=tmp_path,
    )
    strategy = create_strategy(config)
    base_parameters = parameters_to_ndarrays(strategy.initial_parameters)
    first = [array + 1.0 for array in base_parameters]
    second = [array + 3.0 for array in base_parameters]
    results = [
        (
            SimpleNamespace(cid="hospital_1"),
            FitRes(
                status=Status(Code.OK, "ok"),
                parameters=ndarrays_to_parameters(first),
                num_examples=10,
                metrics={"node_id": "hospital_1", "loss": 0.4, "accuracy": 0.8},
            ),
        ),
        (
            SimpleNamespace(cid="hospital_2"),
            FitRes(
                status=Status(Code.OK, "ok"),
                parameters=ndarrays_to_parameters(second),
                num_examples=10,
                metrics={"node_id": "hospital_2", "loss": 0.2, "accuracy": 0.9},
            ),
        ),
    ]

    aggregated, metrics = strategy.aggregate_fit(1, results, [])

    assert aggregated is not None
    assert metrics["status"] == "completed"
    assert metrics["participating_clients"] == 2
    assert strategy.artifacts[0].path.exists()
    assert (tmp_path / "training_rounds.jsonl").exists()
