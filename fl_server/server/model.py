"""PyTorch model and parameter conversion utilities for Flower."""

from collections import OrderedDict

import numpy as np
import torch
from torch import nn


class HealthcareMLP(nn.Module):
    """Binary clinical classifier used by federated hospital clients."""

    def __init__(
        self,
        input_dim: int,
        *,
        hidden_dims: tuple[int, int] = (32, 16),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dims[0]),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dims[0], hidden_dims[1]),
            nn.ReLU(),
            nn.Linear(hidden_dims[1], 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features).squeeze(-1)


def create_model(input_dim: int) -> HealthcareMLP:
    return HealthcareMLP(input_dim=input_dim)


def get_model_parameters(model: nn.Module) -> list[np.ndarray]:
    """Extract model state as NumPy arrays for Flower transport."""

    return [parameter.detach().cpu().numpy().copy() for parameter in model.state_dict().values()]


def set_model_parameters(model: nn.Module, parameters: list[np.ndarray]) -> None:
    """Load Flower parameter arrays into a PyTorch model."""

    state_dict_keys = list(model.state_dict().keys())
    if len(state_dict_keys) != len(parameters):
        raise ValueError(
            f"Expected {len(state_dict_keys)} parameter tensors, received {len(parameters)}"
        )
    state_dict = OrderedDict(
        (key, torch.as_tensor(value))
        for key, value in zip(state_dict_keys, parameters, strict=True)
    )
    model.load_state_dict(state_dict, strict=True)
