"""FedAvg and Weighted FedAvg aggregation implementations."""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ClientUpdate:
    """One hospital node's model update and non-identifying metrics."""

    node_id: str
    parameters: list[np.ndarray]
    num_examples: int
    metrics: dict[str, Any]


def _validate_updates(updates: list[ClientUpdate]) -> None:
    if not updates:
        raise ValueError("At least one client update is required for aggregation")
    expected_shapes = [array.shape for array in updates[0].parameters]
    if not expected_shapes:
        raise ValueError("Client updates must include model parameters")
    for update in updates:
        if update.num_examples <= 0:
            raise ValueError(f"Client {update.node_id} reported no training examples")
        shapes = [array.shape for array in update.parameters]
        if shapes != expected_shapes:
            raise ValueError(
                f"Client {update.node_id} parameter shapes do not match the global model"
            )


def aggregate_fedavg(updates: list[ClientUpdate]) -> list[np.ndarray]:
    """Average every participating hospital equally."""

    _validate_updates(updates)
    aggregated: list[np.ndarray] = []
    for tensors in zip(*(update.parameters for update in updates), strict=True):
        stacked = np.stack(tensors, axis=0)
        aggregated.append(np.mean(stacked, axis=0).astype(tensors[0].dtype, copy=False))
    return aggregated


def aggregate_weighted_fedavg(updates: list[ClientUpdate]) -> list[np.ndarray]:
    """Average hospital updates weighted by each node's local training examples."""

    _validate_updates(updates)
    total_examples = sum(update.num_examples for update in updates)
    aggregated: list[np.ndarray] = []
    for tensors in zip(*(update.parameters for update in updates), strict=True):
        weighted_sum = np.zeros_like(tensors[0], dtype=np.float64)
        for tensor, update in zip(tensors, updates, strict=True):
            weighted_sum += tensor.astype(np.float64) * (update.num_examples / total_examples)
        aggregated.append(weighted_sum.astype(tensors[0].dtype, copy=False))
    return aggregated


def aggregate_client_metrics(
    updates: list[ClientUpdate],
) -> dict[str, float | int | dict[str, Any]]:
    """Aggregate scalar metrics while preserving per-node metric details."""

    _validate_updates(updates)
    total_examples = sum(update.num_examples for update in updates)
    scalar_metric_names = ("loss", "accuracy", "precision", "recall", "f1", "roc_auc")
    aggregated: dict[str, float | int | dict[str, Any]] = {
        "total_examples": total_examples,
        "participating_clients": len(updates),
        "client_metrics": {update.node_id: update.metrics for update in updates},
    }
    for metric_name in scalar_metric_names:
        values = [
            float(update.metrics[metric_name]) * (update.num_examples / total_examples)
            for update in updates
            if metric_name in update.metrics
        ]
        if values:
            aggregated[metric_name] = float(sum(values))
    return aggregated
