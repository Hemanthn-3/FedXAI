"""Local PyTorch training and evaluation loops used by hospital clients."""

import random

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from fl_server.server.dataset import FederatedDataset
from fl_server.server.metrics import BinaryMetrics, compute_binary_metrics


def set_training_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _data_loader(
    x: np.ndarray,
    y: np.ndarray,
    *,
    batch_size: int,
    shuffle: bool,
) -> DataLoader:
    dataset = TensorDataset(
        torch.as_tensor(x, dtype=torch.float32),
        torch.as_tensor(y, dtype=torch.float32),
    )
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def train_local_model(
    model: nn.Module,
    dataset: FederatedDataset,
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    device: str = "cpu",
) -> float:
    """Train a model only on one hospital node's local data."""

    model.to(device)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()
    last_loss = 0.0
    for _ in range(epochs):
        for x_batch, y_batch in _data_loader(
            dataset.x_train,
            dataset.y_train,
            batch_size=batch_size,
            shuffle=True,
        ):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)
            optimizer.zero_grad()
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            last_loss = float(loss.detach().cpu().item())
    return last_loss


def evaluate_model(
    model: nn.Module,
    dataset: FederatedDataset,
    *,
    batch_size: int,
    device: str = "cpu",
) -> BinaryMetrics:
    """Evaluate a local or global model on one hospital node's test split."""

    model.to(device)
    model.eval()
    criterion = nn.BCEWithLogitsLoss(reduction="sum")
    losses: list[float] = []
    probabilities: list[float] = []
    labels: list[float] = []
    with torch.no_grad():
        for x_batch, y_batch in _data_loader(
            dataset.x_test,
            dataset.y_test,
            batch_size=batch_size,
            shuffle=False,
        ):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)
            logits = model(x_batch)
            loss = criterion(logits, y_batch)
            losses.append(float(loss.detach().cpu().item()))
            probabilities.extend(torch.sigmoid(logits).detach().cpu().numpy().tolist())
            labels.extend(y_batch.detach().cpu().numpy().tolist())
    mean_loss = sum(losses) / max(1, len(labels))
    return compute_binary_metrics(
        np.asarray(labels, dtype=np.float32),
        np.asarray(probabilities, dtype=np.float32),
        loss=mean_loss,
    )
