import pandas as pd

from backend.app.models.enums import DatasetType
from fl_server.server.config import FederatedLearningConfig
from fl_server.server.dataset import load_healthcare_csv
from hospital_nodes.client import build_client


def _heart_dataframe(rows: int = 30) -> pd.DataFrame:
    records = []
    for index in range(rows):
        target = index % 2
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
                "target": target,
            }
        )
    return pd.DataFrame.from_records(records)


def test_load_healthcare_csv_validates_and_preprocesses_heart_dataset(tmp_path) -> None:
    path = tmp_path / "heart.csv"
    _heart_dataframe().to_csv(path, index=False)

    dataset = load_healthcare_csv(path, dataset_type=DatasetType.HEART_DISEASE)

    assert dataset.input_dim == 9
    assert dataset.train_examples > dataset.test_examples
    assert dataset.feature_names == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "chol",
        "fbs",
        "thalach",
        "exang",
        "oldpeak",
    )


def test_hospital_client_trains_and_evaluates_without_sharing_rows(tmp_path) -> None:
    path = tmp_path / "heart.csv"
    _heart_dataframe(36).to_csv(path, index=False)
    config = FederatedLearningConfig(epochs=1, batch_size=8, clients=1, rounds=1)
    client = build_client(
        node_id="hospital_test",
        data_path=path,
        dataset_type=DatasetType.HEART_DISEASE,
        config=config,
    )
    initial_parameters = client.get_parameters({})

    updated_parameters, train_examples, fit_metrics = client.fit(initial_parameters, {})
    loss, test_examples, eval_metrics = client.evaluate(updated_parameters, {})

    assert train_examples == client.dataset.train_examples
    assert test_examples == client.dataset.test_examples
    assert len(updated_parameters) == len(initial_parameters)
    assert fit_metrics["node_id"] == "hospital_test"
    assert "accuracy" in fit_metrics
    assert isinstance(loss, float)
    assert "roc_auc" in eval_metrics
