"""Flower server entrypoint for FedPedia-XAI."""

import argparse
import logging
from pathlib import Path

import flwr as fl
import torch
from flwr.common import ndarrays_to_parameters

from fl_server.server.config import FederatedLearningConfig
from fl_server.server.dataset import schema_for
from fl_server.server.enums import AggregationStrategy, DatasetType
from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.persistence import FLPersistence
from fl_server.server.registry import ModelRegistry
from fl_server.server.strategy import FedPediaFedAvgStrategy, resolve_preprocessing

logger = logging.getLogger(__name__)


def _load_initial_state(path: Path, input_dim: int) -> tuple[list, dict] | None:
    """Load state arrays + preprocessing metadata from a saved model artifact."""

    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
        except Exception as exc:
            logger.warning("Could not load active model artifact %s: %s", path, exc)
            return None
    state_dict = payload.get("state_dict")
    artifact_dim = int(payload.get("input_dim", input_dim))
    if not state_dict or artifact_dim != input_dim:
        logger.warning(
            "Active model artifact %s does not match expected input_dim=%d; "
            "falling back to a fresh initial model.",
            path,
            input_dim,
        )
        return None
    model = create_model(input_dim)
    model.load_state_dict(state_dict, strict=True)
    return get_model_parameters(model), dict(payload.get("preprocessing") or {})


def create_strategy(config: FederatedLearningConfig) -> FedPediaFedAvgStrategy:
    """Create a fully configured Flower strategy for the selected dataset.

    Step 1 of the federated lifecycle: if the database holds an active global
    model (bootstrap or a previous run's best), round 1 starts from its weights
    and carries its preprocessing spec to every client.
    """

    schema = schema_for(config.dataset_type)
    persistence = FLPersistence(
        config.database_url,
        dataset_type=config.dataset_type.value,
        total_clients=config.clients,
        aggregation_strategy=config.aggregation_strategy.value,
    )

    initial_parameters = ndarrays_to_parameters(
        get_model_parameters(create_model(schema.input_dim))
    )
    preprocessing: dict = {"type": "identity"}

    active_path = persistence.load_active_model_path()
    if active_path:
        loaded = _load_initial_state(Path(active_path), schema.input_dim)
        if loaded is not None:
            state_arrays, artifact_preprocessing = loaded
            initial_parameters = ndarrays_to_parameters(state_arrays)
            preprocessing = artifact_preprocessing
            logger.info("Round 0 seeded from active model: %s", active_path)
        else:
            logger.warning("Active model unusable (%s); starting from random init.", active_path)
    else:
        logger.info("No active global model found; starting from random init.")

    return FedPediaFedAvgStrategy(
        config=config,
        input_dim=schema.input_dim,
        registry=ModelRegistry(config.artifact_root),
        initial_parameters=initial_parameters,
        preprocessing=resolve_preprocessing(preprocessing, schema.input_dim),
        persistence=persistence,
    )


def run_server(config: FederatedLearningConfig | None = None) -> fl.server.History:
    """Start the Flower aggregation server.

    If ``config.use_mtls`` is True the server will require every connecting
    hospital node to present a valid client certificate signed by the shared CA
    (mutual TLS).  Certificate paths are resolved from env vars via
    ``FederatedLearningConfig``.
    """
    resolved = config or FederatedLearningConfig.from_settings()
    strategy = create_strategy(resolved)

    # Lifecycle bookkeeping: fresh run_id + clear prior round rows, then after
    # the run completes activate the best-scoring model for predictions.
    strategy.persistence.begin_run()

    # Build optional mTLS certificate bundle
    ssl_certificates: tuple[bytes, bytes, bytes] | None = None
    if resolved.use_mtls:
        if not (resolved.ca_cert_path and resolved.server_cert_path and resolved.server_key_path):
            raise ValueError(
                "mTLS is enabled (FL_USE_MTLS=true) but one or more certificate paths are "
                "missing.  Set FL_CA_CERT_PATH, FL_SERVER_CERT_PATH, FL_SERVER_KEY_PATH."
            )
        ca_cert = resolved.ca_cert_path.read_bytes()
        server_cert = resolved.server_cert_path.read_bytes()
        server_key = resolved.server_key_path.read_bytes()
        ssl_certificates = (ca_cert, server_cert, server_key)

    history = fl.server.start_server(
        server_address=resolved.server_address,
        config=fl.server.ServerConfig(num_rounds=resolved.rounds),
        strategy=strategy,
        certificates=ssl_certificates,
    )
    strategy.persistence.activate_best()
    return history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FedPedia-XAI Flower server")
    parser.add_argument("--server-address", default=None)
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--clients", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument(
        "--dataset-type",
        choices=[item.value for item in DatasetType],
        default=None,
    )
    parser.add_argument(
        "--aggregation-strategy",
        choices=[item.value for item in AggregationStrategy],
        default=None,
    )
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = FederatedLearningConfig.from_settings()
    config = FederatedLearningConfig(
        server_address=args.server_address or base.server_address,
        rounds=args.rounds or base.rounds,
        clients=args.clients or base.clients,
        epochs=args.epochs or base.epochs,
        batch_size=args.batch_size or base.batch_size,
        lr=args.lr or base.lr,
        dataset_type=DatasetType(args.dataset_type) if args.dataset_type else base.dataset_type,
        aggregation_strategy=AggregationStrategy(args.aggregation_strategy)
        if args.aggregation_strategy
        else base.aggregation_strategy,
        artifact_root=args.artifact_root or base.artifact_root,
        test_size=base.test_size,
        random_state=base.random_state,
        database_url=base.database_url,
    )
    run_server(config)


if __name__ == "__main__":
    main()
