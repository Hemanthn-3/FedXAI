"""Differential Privacy utilities for federated gradient aggregation.

These helpers implement two key DP-SGD operations applied at the FL server
during aggregation (not at the hospital client side):

1. Gradient Clipping  — bounding each individual client update's L2 norm to a
   maximum value ``max_grad_norm``.  This limits the sensitivity of each
   participant's contribution so that the added noise provides a meaningful
   privacy guarantee.

2. Gaussian Noise Addition — injecting zero-mean Gaussian noise with standard
   deviation  σ = noise_scale × max_grad_norm / num_clients  to the aggregated
   parameters.  The divisor ``num_clients`` accounts for the fact that FedAvg
   averages (not sums) updates, keeping the signal-to-noise ratio stable.

Mathematical guarantee:
    The resulting mechanism is (ε, δ)-differentially private.  The exact values
    of ε and δ depend on the chosen ``noise_scale``, ``max_grad_norm``, number
    of training rounds, and dataset size.  Lower ``noise_scale`` means stronger
    privacy (higher noise → smaller ε) at the cost of model accuracy.

Typical usage (inside ``FedPediaFedAvgStrategy.aggregate_fit``):
    dp = DifferentialPrivacy(noise_scale=1.0, max_grad_norm=1.0)
    clipped_updates = [dp.clip_gradients(u.parameters) for u in updates]
    noisy_aggregated = dp.add_gaussian_noise(aggregated_parameters, num_clients=3)
"""

import numpy as np


class DifferentialPrivacy:
    """Server-side DP gradient processor for FedAvg-style aggregation."""

    def __init__(self, *, noise_scale: float = 1.0, max_grad_norm: float = 1.0) -> None:
        """
        Args:
            noise_scale: Gaussian noise multiplier (σ / max_grad_norm).
                         Higher values → more privacy, lower model accuracy.
                         Recommended starting point: 0.5–2.0.
            max_grad_norm: Maximum L2 norm for individual client parameter
                           vectors (clipping threshold).  Recommended: 0.1–5.0.
        """
        if noise_scale < 0:
            raise ValueError("noise_scale must be >= 0 (use 0 to disable noise).")
        if max_grad_norm <= 0:
            raise ValueError("max_grad_norm must be > 0.")
        self.noise_scale = noise_scale
        self.max_grad_norm = max_grad_norm

    def clip_gradients(self, parameters: list[np.ndarray]) -> list[np.ndarray]:
        """Clip a single client's parameter list so its total L2 norm ≤ max_grad_norm.

        Args:
            parameters: List of NumPy arrays (one per model layer) from one client.

        Returns:
            New list of arrays with the same shapes, scaled so that the global
            L2 norm across all layers does not exceed ``max_grad_norm``.
        """
        # Compute global L2 norm across all parameter tensors for this client.
        total_norm = float(
            np.sqrt(sum(np.sum(p ** 2) for p in parameters))
        )
        # Scaling factor — if already within bound, clip_coeff == 1.0 (no-op).
        clip_coeff = min(1.0, self.max_grad_norm / (total_norm + 1e-9))
        return [p * clip_coeff for p in parameters]

    def add_gaussian_noise(
        self,
        aggregated: list[np.ndarray],
        *,
        num_clients: int,
    ) -> list[np.ndarray]:
        """Add calibrated Gaussian noise to already-aggregated parameters.

        The standard deviation is σ = noise_scale × max_grad_norm / num_clients.
        Dividing by num_clients is correct because FedAvg *averages* updates;
        the aggregated sensitivity is therefore max_grad_norm / num_clients.

        Args:
            aggregated: List of NumPy arrays (global model parameters after FedAvg).
            num_clients: Number of clients that contributed to this round.

        Returns:
            List of arrays with added Gaussian noise.
        """
        if self.noise_scale == 0.0:
            return aggregated
        sigma = self.noise_scale * self.max_grad_norm / max(1, num_clients)
        rng = np.random.default_rng()
        return [p + rng.normal(0, sigma, size=p.shape).astype(p.dtype) for p in aggregated]
