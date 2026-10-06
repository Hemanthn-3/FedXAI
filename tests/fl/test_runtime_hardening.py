"""Differential privacy, client mTLS transport, and hospital node utilities."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from fl_server.server.dp import DifferentialPrivacy
from hospital_nodes.client import _load_mtls_certs, parse_client_args

# ---------------------------------------------------------------------------
# Differential privacy
# ---------------------------------------------------------------------------


def test_dp_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError, match="noise_scale"):
        DifferentialPrivacy(noise_scale=-0.1)
    with pytest.raises(ValueError, match="max_grad_norm"):
        DifferentialPrivacy(max_grad_norm=0.0)


def test_clip_gradients_bounds_global_l2_norm() -> None:
    dp = DifferentialPrivacy(noise_scale=0.0, max_grad_norm=1.0)
    big = [np.full((4, 4), 10.0), np.full((3,), 10.0)]
    clipped = dp.clip_gradients(big)
    norm = float(np.sqrt(sum(float(np.sum(p**2)) for p in clipped)))
    assert norm <= 1.0 + 1e-6
    assert [p.shape for p in clipped] == [p.shape for p in big]


def test_clip_gradients_leaves_small_updates_untouched() -> None:
    dp = DifferentialPrivacy(noise_scale=0.0, max_grad_norm=1.0)
    small = [np.full((2,), 0.1)]
    clipped = dp.clip_gradients(small)
    assert all(
        np.allclose(a, b) for a, b in zip(clipped, small, strict=True)
    )


def test_add_gaussian_noise_zero_scale_returns_input() -> None:
    dp = DifferentialPrivacy(noise_scale=0.0, max_grad_norm=1.0)
    agg = [np.ones((2, 2))]
    assert dp.add_gaussian_noise(agg, num_clients=3)[0] is agg[0]


def test_add_gaussian_noise_preserves_shape_and_perturbs() -> None:
    dp = DifferentialPrivacy(noise_scale=1.0, max_grad_norm=1.0)
    agg = [np.zeros((5, 5)), np.zeros((3,))]
    noisy = dp.add_gaussian_noise(agg, num_clients=3)
    assert [n.shape for n in noisy] == [a.shape for a in agg]
    assert not np.allclose(noisy[0], agg[0])


# ---------------------------------------------------------------------------
# Client mTLS transport
# ---------------------------------------------------------------------------


def test_client_mtls_disabled_defaults_to_insecure(monkeypatch) -> None:
    monkeypatch.delenv("FL_USE_MTLS", raising=False)
    assert _load_mtls_certs() == {"insecure": True}


def test_client_mtls_requires_ca_certificate(monkeypatch) -> None:
    monkeypatch.setenv("FL_USE_MTLS", "true")
    monkeypatch.delenv("FL_CA_CERT_PATH", raising=False)
    with pytest.raises(ValueError, match="FL_CA_CERT_PATH"):
        _load_mtls_certs()


def test_client_mtls_server_authentication_only(monkeypatch, tmp_path) -> None:
    ca = tmp_path / "ca.crt"
    ca.write_bytes(b"CA-BYTES")
    monkeypatch.setenv("FL_USE_MTLS", "true")
    monkeypatch.setenv("FL_CA_CERT_PATH", str(ca))
    monkeypatch.delenv("FL_CLIENT_CERT_PATH", raising=False)
    monkeypatch.delenv("FL_CLIENT_KEY_PATH", raising=False)
    assert _load_mtls_certs() == {"root_certificates": b"CA-BYTES"}


def test_client_mtls_mutual_authentication(monkeypatch, tmp_path) -> None:
    ca = tmp_path / "ca.crt"
    ca.write_bytes(b"CA")
    cert = tmp_path / "node.crt"
    cert.write_bytes(b"CERT")
    key = tmp_path / "node.key"
    key.write_bytes(b"KEY")
    monkeypatch.setenv("FL_USE_MTLS", "true")
    monkeypatch.setenv("FL_CA_CERT_PATH", str(ca))
    monkeypatch.setenv("FL_CLIENT_CERT_PATH", str(cert))
    monkeypatch.setenv("FL_CLIENT_KEY_PATH", str(key))
    assert _load_mtls_certs() == {
        "root_certificates": b"CA",
        "certificate_chain": b"CERT",
        "private_key": b"KEY",
    }


# ---------------------------------------------------------------------------
# Client argument parsing
# ---------------------------------------------------------------------------


def test_parse_client_args_defaults(monkeypatch) -> None:
    for name in (
        "HOSPITAL_NODE_ID",
        "HOSPITAL_DATA_PATH",
        "FL_DATASET_TYPE",
        "FL_SERVER_ADDRESS",
        "FL_DEVICE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["prog"])

    args = parse_client_args("hospital_1", "hospital_nodes/node_1/data.csv")
    assert args.node_id == "hospital_1"
    assert args.data_path == "hospital_nodes/node_1/data.csv"
    assert args.dataset_type == "heart_disease"
    assert args.server_address == "127.0.0.1:8080"
    assert args.device == "cpu"


def test_parse_client_args_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("HOSPITAL_NODE_ID", "hospital_2")
    monkeypatch.setattr(sys, "argv", ["prog"])

    args = parse_client_args("hospital_1", "x.csv")
    assert args.node_id == "hospital_2"


# ---------------------------------------------------------------------------
# Mock data generation + node entrypoints
# ---------------------------------------------------------------------------


def test_generate_hospital_data_writes_deterministic_csv(tmp_path) -> None:
    from hospital_nodes.generate_mock_data import generate_hospital_data

    target = tmp_path / "hospital" / "data.csv"
    generate_hospital_data(target, rows=30, seed=7)
    first = pd.read_csv(target)
    generate_hospital_data(target, rows=30, seed=7)
    second = pd.read_csv(target)

    assert len(first) == 30
    assert set(first["target"].unique()) == {0, 1}
    assert {"age", "oldpeak", "target"} <= set(first.columns)
    pd.testing.assert_frame_equal(first, second)


def test_node_entrypoints_are_importable() -> None:
    import hospital_nodes.node_1.client  # noqa: F401
    import hospital_nodes.node_2.client  # noqa: F401
    import hospital_nodes.node_3.client  # noqa: F401
