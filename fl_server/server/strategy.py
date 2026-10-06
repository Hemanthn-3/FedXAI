"""Flower strategy that applies FedPedia-XAI aggregation and model storage."""

import json
from typing import Any

from flwr.common import FitRes, Parameters, Scalar, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg

from fl_server.server.aggregation import (
    ClientUpdate,
    aggregate_client_metrics,
    aggregate_fedavg,
    aggregate_weighted_fedavg,
)
from fl_server.server.config import FederatedLearningConfig
from fl_server.server.dp import DifferentialPrivacy
from fl_server.server.enums import AggregationStrategy
from fl_server.server.persistence import FLPersistence
from fl_server.server.registry import ModelArtifact, ModelRegistry


def resolve_preprocessing(
    preprocessing: dict[str, Any] | None,
    input_dim: int,
) -> dict[str, Any]:
    """Validate a preprocessing spec against the model input dimension.

    Falls back to an identity spec when the spec is missing or malformed so
    clients never receive a transform they cannot apply.
    """

    identity = {
        "type": "identity",
        "means": [0.0] * input_dim,
        "scales": [1.0] * input_dim,
    }
    if not preprocessing:
        return identity
    kind = str(preprocessing.get("type", "identity")).lower()
    if kind == "identity":
        return identity
    if kind == "standardization":
        means = preprocessing.get("means") or []
        scales = preprocessing.get("scales") or []
        if len(means) != input_dim or len(scales) != input_dim:
            return identity
        return dict(preprocessing)
    return identity


class FedPediaFedAvgStrategy(FedAvg):
    """Flower strategy implementing FedAvg, Weighted FedAvg, and artifact storage."""

    def __init__(
        self,
        *,
        config: FederatedLearningConfig,
        input_dim: int,
        registry: ModelRegistry,
        initial_parameters: Parameters,
        preprocessing: dict[str, Any] | None = None,
        persistence: FLPersistence | None = None,
    ) -> None:
        self.preprocessing = resolve_preprocessing(preprocessing, input_dim)
        preprocessing_json = json.dumps(self.preprocessing)

        def fit_config(_round: int) -> dict[str, Scalar]:
            payload: dict[str, Scalar] = dict(config.fit_config())
            payload["preprocessing"] = preprocessing_json
            return payload

        super().__init__(
            fraction_fit=1.0,
            fraction_evaluate=1.0,
            min_fit_clients=config.clients,
            min_evaluate_clients=config.clients,
            min_available_clients=config.clients,
            on_fit_config_fn=fit_config,
            on_evaluate_config_fn=fit_config,
            accept_failures=False,
            initial_parameters=initial_parameters,
            inplace=False,
        )
        self.config = config
        self.input_dim = input_dim
        self.registry = registry
        self.persistence = persistence or FLPersistence(
            None,
            dataset_type=config.dataset_type.value,
            total_clients=config.clients,
            aggregation_strategy=config.aggregation_strategy.value,
        )
        self.artifacts: list[ModelArtifact] = []
        self.round_metrics_history: list[dict[str, Any]] = []

    @staticmethod
    def _update_from_result(client: ClientProxy, fit_res: FitRes) -> ClientUpdate:
        metrics = dict(fit_res.metrics)
        node_id = str(metrics.get("node_id", client.cid))
        return ClientUpdate(
            node_id=node_id,
            parameters=parameters_to_ndarrays(fit_res.parameters),
            num_examples=int(fit_res.num_examples),
            metrics=metrics,
        )

    @staticmethod
    def _flower_scalars(metrics: dict[str, Any]) -> dict[str, Scalar]:
        allowed: dict[str, Scalar] = {}
        for key, value in metrics.items():
            if isinstance(value, bool | bytes | float | int | str):
                allowed[key] = value
        return allowed

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate fit results, persist global model, and return updated parameters."""

        if failures:
            failure_count = len(failures)
            self.registry.record_round_metrics(
                round_number=server_round,
                dataset_type=self.config.dataset_type,
                aggregation_strategy=self.config.aggregation_strategy.value,
                metrics={"status": "failed", "failures": failure_count},
                artifact=None,
            )
            self.persistence.register_round(
                round_number=server_round,
                metrics={"failures": failure_count},
                status="failed",
            )
            return None, {"status": "failed", "failures": failure_count}
        if not results:
            return None, {"status": "no_results"}

        updates = [self._update_from_result(client, fit_res) for client, fit_res in results]

        # ── Differential Privacy: clip individual updates then add noise ─────────
        if self.config.dp_enabled:
            dp = DifferentialPrivacy(
                noise_scale=self.config.dp_noise_scale,
                max_grad_norm=self.config.dp_max_grad_norm,
            )
            # ClientUpdate is frozen, so build new instances with clipped parameters
            from dataclasses import replace as dataclass_replace
            updates = [
                dataclass_replace(u, parameters=dp.clip_gradients(u.parameters))
                for u in updates
            ]

        # ── FedAvg aggregation ────────────────────────────────────────────────
        if self.config.aggregation_strategy == AggregationStrategy.WEIGHTED_FEDAVG:
            aggregated_parameters = aggregate_weighted_fedavg(updates)
        else:
            aggregated_parameters = aggregate_fedavg(updates)

        # ── Differential Privacy: add Gaussian noise to aggregated result ──────
        if self.config.dp_enabled:
            aggregated_parameters = dp.add_gaussian_noise(
                aggregated_parameters,
                num_clients=len(updates),
            )

        aggregated_metrics = aggregate_client_metrics(updates)
        artifact = self.registry.save_global_model(
            parameters=aggregated_parameters,
            input_dim=self.input_dim,
            dataset_type=self.config.dataset_type,
            round_number=server_round,
            metrics=aggregated_metrics,
            preprocessing=self.preprocessing,
        )
        aggregated_metrics.update(
            {
                "status": "completed",
                "round_number": server_round,
                "model_version": artifact.version,
                "model_path": str(artifact.path),
                "model_checksum_sha256": artifact.checksum_sha256,
                # Differential Privacy provenance
                "dp_enabled": self.config.dp_enabled,
                "dp_noise_scale": self.config.dp_noise_scale if self.config.dp_enabled else None,
                "dp_max_grad_norm": (
                    self.config.dp_max_grad_norm if self.config.dp_enabled else None
                ),
            }
        )
        self.registry.record_round_metrics(
            round_number=server_round,
            dataset_type=self.config.dataset_type,
            aggregation_strategy=self.config.aggregation_strategy.value,
            metrics=aggregated_metrics,
            artifact=artifact,
        )
        self.persistence.register_round(
            round_number=server_round,
            metrics=aggregated_metrics,
            artifact_version=artifact.version,
            artifact_path=artifact.path,
            artifact_checksum=artifact.checksum_sha256,
            status="completed",
        )
        self.artifacts.append(artifact)
        self.round_metrics_history.append(aggregated_metrics)
        return (
            ndarrays_to_parameters(aggregated_parameters),
            self._flower_scalars(aggregated_metrics),
        )
