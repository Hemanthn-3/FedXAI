"""Reusable Flower client for isolated hospital nodes."""

import argparse
import json
import os
from pathlib import Path

import flwr as fl
import numpy as np
from flwr.common import Scalar

from fl_server.server.enums import DatasetType
from fl_server.server.config import FederatedLearningConfig
from fl_server.server.dataset import FederatedDataset, load_healthcare_csv
from fl_server.server.model import create_model, get_model_parameters, set_model_parameters
from fl_server.server.training import evaluate_model, set_training_seed, train_local_model


class HospitalFlowerClient(fl.client.NumPyClient):
    """Flower NumPyClient that trains only on one hospital's local data."""

    def __init__(
        self,
        *,
        node_id: str,
        dataset: FederatedDataset,
        config: FederatedLearningConfig,
        device: str = "cpu",
    ) -> None:
        self.node_id = node_id
        self.dataset = dataset
        self.config = config
        self.device = device
        set_training_seed(config.random_state)
        self.model = create_model(dataset.input_dim)

    def get_parameters(self, config: dict[str, Scalar]) -> list[np.ndarray]:
        return get_model_parameters(self.model)

    def fit(
        self,
        parameters: list[np.ndarray],
        config: dict[str, Scalar],
    ) -> tuple[list[np.ndarray], int, dict[str, Scalar]]:
        set_model_parameters(self.model, parameters)
        epochs = int(config.get("epochs", self.config.epochs))
        batch_size = int(config.get("batch_size", self.config.batch_size))
        lr = float(config.get("lr", self.config.lr))
        train_loss = train_local_model(
            self.model,
            self.dataset,
            epochs=epochs,
            batch_size=batch_size,
            lr=lr,
            device=self.device,
        )
        metrics = evaluate_model(
            self.model,
            self.dataset,
            batch_size=batch_size,
            device=self.device,
        )
        metric_payload: dict[str, Scalar] = {
            "node_id": self.node_id,
            "dataset_type": self.dataset.dataset_type.value,
            "train_examples": self.dataset.train_examples,
            "test_examples": self.dataset.test_examples,
            "train_loss": float(train_loss),
            "loss": float(metrics.loss),
            "accuracy": float(metrics.accuracy),
            "precision": float(metrics.precision),
            "recall": float(metrics.recall),
            "f1": float(metrics.f1),
            "roc_auc": float(metrics.roc_auc),
            "confusion_matrix_json": json.dumps(metrics.confusion_matrix),
        }
        return get_model_parameters(self.model), self.dataset.train_examples, metric_payload

    def evaluate(
        self,
        parameters: list[np.ndarray],
        config: dict[str, Scalar],
    ) -> tuple[float, int, dict[str, Scalar]]:
        set_model_parameters(self.model, parameters)
        batch_size = int(config.get("batch_size", self.config.batch_size))
        metrics = evaluate_model(
            self.model,
            self.dataset,
            batch_size=batch_size,
            device=self.device,
        )
        return (
            float(metrics.loss),
            self.dataset.test_examples,
            {
                "node_id": self.node_id,
                "accuracy": float(metrics.accuracy),
                "precision": float(metrics.precision),
                "recall": float(metrics.recall),
                "f1": float(metrics.f1),
                "roc_auc": float(metrics.roc_auc),
                "confusion_matrix_json": json.dumps(metrics.confusion_matrix),
            },
        )


def build_client(
    *,
    node_id: str,
    data_path: str | Path,
    dataset_type: DatasetType,
    config: FederatedLearningConfig,
    device: str = "cpu",
) -> HospitalFlowerClient:
    """Create a hospital client from a local CSV path."""

    dataset = load_healthcare_csv(
        data_path,
        dataset_type=dataset_type,
        test_size=config.test_size,
        random_state=config.random_state,
    )
    return HospitalFlowerClient(
        node_id=node_id,
        dataset=dataset,
        config=config,
        device=device,
    )


def _load_mtls_certs() -> dict:
    """Build keyword arguments for fl.client.start_numpy_client transport security.

    When FL_USE_MTLS=true the client authenticates the server via the shared CA
    certificate and optionally presents its own client certificate for mutual TLS.

    Returns an empty dict when mTLS is disabled (insecure development mode).
    """
    use_mtls = os.getenv("FL_USE_MTLS", "false").lower() in {"1", "true", "yes"}
    if not use_mtls:
        return {"insecure": True}

    ca_cert_path = os.getenv("FL_CA_CERT_PATH")
    if not ca_cert_path:
        raise ValueError(
            "FL_USE_MTLS=true but FL_CA_CERT_PATH is not set.  "
            "Point it at the shared CA certificate (certs/ca.crt)."
        )
    root_certificates = Path(ca_cert_path).read_bytes()

    # Optional: mutual TLS — client presents its own cert to the server
    client_cert_path = os.getenv("FL_CLIENT_CERT_PATH")
    client_key_path = os.getenv("FL_CLIENT_KEY_PATH")
    if client_cert_path and client_key_path:
        return {
            "root_certificates": root_certificates,
            "certificate_chain": Path(client_cert_path).read_bytes(),
            "private_key": Path(client_key_path).read_bytes(),
        }

    # Server-authentication only (no client cert)
    return {"root_certificates": root_certificates}


def run_client(
    *,
    node_id: str,
    data_path: str | Path,
    dataset_type: DatasetType,
    server_address: str,
    config: FederatedLearningConfig | None = None,
    device: str = "cpu",
) -> None:
    """Connect this hospital node to the Flower server."""

    resolved = config or FederatedLearningConfig.from_settings()
    client = build_client(
        node_id=node_id,
        data_path=data_path,
        dataset_type=dataset_type,
        config=resolved,
        device=device,
    )
    transport_kwargs = _load_mtls_certs()
    fl.client.start_numpy_client(
        server_address=server_address,
        client=client,
        **transport_kwargs,
    )


def parse_client_args(default_node_id: str, default_data_path: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {default_node_id} Flower client")
    parser.add_argument("--node-id", default=os.getenv("HOSPITAL_NODE_ID", default_node_id))
    parser.add_argument("--data-path", default=os.getenv("HOSPITAL_DATA_PATH", default_data_path))
    parser.add_argument(
        "--dataset-type",
        choices=[item.value for item in DatasetType],
        default=os.getenv("FL_DATASET_TYPE", DatasetType.HEART_DISEASE.value),
    )
    parser.add_argument(
        "--server-address",
        default=os.getenv("FL_SERVER_ADDRESS", "127.0.0.1:8080"),
    )
    parser.add_argument("--device", default=os.getenv("FL_DEVICE", "cpu"))
    return parser.parse_args()


def run_node_from_args(default_node_id: str, default_data_path: str) -> None:
    args = parse_client_args(default_node_id, default_data_path)
    run_client(
        node_id=args.node_id,
        data_path=args.data_path,
        dataset_type=DatasetType(args.dataset_type),
        server_address=args.server_address,
        device=args.device,
    )
