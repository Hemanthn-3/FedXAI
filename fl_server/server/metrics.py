"""Model evaluation metrics for federated and centralized comparison."""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass(frozen=True)
class BinaryMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    loss: float
    confusion_matrix: list[list[int]]

    def as_dict(self) -> dict[str, float | list[list[int]]]:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "loss": self.loss,
            "confusion_matrix": self.confusion_matrix,
        }


def compute_binary_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    loss: float,
    threshold: float = 0.5,
) -> BinaryMetrics:
    """Compute required binary classification metrics."""

    true = y_true.astype(int)
    probs = probabilities.astype(float)
    predicted = (probs >= threshold).astype(int)
    try:
        roc_auc = float(roc_auc_score(true, probs))
    except ValueError:
        roc_auc = 0.5
    matrix = confusion_matrix(true, predicted, labels=[0, 1]).astype(int).tolist()
    return BinaryMetrics(
        accuracy=float(accuracy_score(true, predicted)),
        precision=float(precision_score(true, predicted, zero_division=0)),
        recall=float(recall_score(true, predicted, zero_division=0)),
        f1=float(f1_score(true, predicted, zero_division=0)),
        roc_auc=roc_auc,
        loss=float(loss),
        confusion_matrix=matrix,
    )
