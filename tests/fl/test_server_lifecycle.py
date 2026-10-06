"""Database-backed FL server lifecycle: persistence, seeding, and activation.

These tests run the real FL persistence stack against a synchronous SQLite
database, mirroring how the Flower server talks to Postgres in production.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import flwr as fl
import pytest
import torch
from flwr.common import parameters_to_ndarrays
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import backend.app.models  # noqa: F401
from backend.app.database.base import Base
from backend.app.models.enums import DatasetType, ModelFramework, ModelSource, TrainingRoundStatus
from backend.app.models.global_model import GlobalModel
from backend.app.models.training_round import TrainingRound
from fl_server.server.app import _load_initial_state, create_strategy, main, parse_args, run_server
from fl_server.server.config import FederatedLearningConfig
from fl_server.server.model import create_model, get_model_parameters
from fl_server.server.persistence import FLPersistence
from fl_server.server.registry import ModelRegistry


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"


@pytest.fixture()
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'fl_lifecycle.db'}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    # The active-model partial unique index is Postgres-only (postgresql_where);
    # on SQLite it would enforce full (dataset_type, source) uniqueness and
    # block the multiple federated rows these tests create.
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_global_models_active_dataset_source")
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield url, sessions
    engine.dispose()


def _persistence(url: str) -> FLPersistence:
    return FLPersistence(url, dataset_type="heart_disease", total_clients=3)


def test_persistence_enabled_flag_and_noop_operations() -> None:
    noop = FLPersistence(None, dataset_type="heart_disease", total_clients=3)
    assert not noop.enabled
    assert noop.load_active_model_path() is None
    noop.begin_run()
    noop.register_round(round_number=1, metrics={"accuracy": 0.5}, status="completed")
    assert noop.activate_best() is None


def test_persistence_enabled_without_database_url(db) -> None:
    url, _ = db
    assert _persistence(url).enabled


def test_register_round_persists_model_and_sanitizes_metrics(db) -> None:
    url, sessions = db
    p = _persistence(url)
    p.register_round(
        round_number=1,
        metrics={
            "accuracy": 0.9,
            "precision": 0.88,
            "recall": 0.85,
            "f1": 0.86,
            "roc_auc": 0.91,
            "loss": 0.32,
            "client_metrics": {"hospital_1": {"loss": 0.3}, "hospital_2": {"loss": 0.4}},
        },
        artifact_version="lifecycle-r0001",
        artifact_path="/models/lifecycle-r0001.pt",
        artifact_checksum="a" * 64,
        status="completed",
    )
    # Out-of-constraint values must be stored as NULL rather than break the insert.
    p.register_round(
        round_number=2,
        metrics={"accuracy": 5.0, "loss": -1.0},
        status="completed",
    )

    with sessions() as s:
        rounds = s.execute(
            select(TrainingRound).order_by(TrainingRound.round_number)
        ).scalars().all()
        assert [r.round_number for r in rounds] == [1, 2]
        first = rounds[0]
        assert first.accuracy == pytest.approx(0.9)
        assert first.loss == pytest.approx(0.32)
        assert first.participating_nodes == ["hospital_1", "hospital_2"]
        assert first.participating_clients == 2
        assert first.status == TrainingRoundStatus.COMPLETED
        assert first.completed_at is not None
        second = rounds[1]
        assert second.accuracy is None
        assert second.loss is None

        models = s.execute(select(GlobalModel)).scalars().all()
        assert len(models) == 1
        assert models[0].is_active is False
        assert models[0].metrics["f1"] == pytest.approx(0.86)
        assert "client_metrics" not in models[0].metrics

    p.begin_run()
    with sessions() as s:
        assert s.execute(select(TrainingRound)).scalars().all() == []
        assert len(s.execute(select(GlobalModel)).scalars().all()) == 1


def test_register_round_failed_records_without_model(db) -> None:
    url, sessions = db
    p = _persistence(url)
    p.register_round(round_number=1, metrics={"failures": 2}, status="failed")

    with sessions() as s:
        rounds = s.execute(select(TrainingRound)).scalars().all()
        assert len(rounds) == 1
        assert rounds[0].status == TrainingRoundStatus.FAILED
        assert rounds[0].participating_clients == 0
        assert rounds[0].completed_at is not None
        assert rounds[0].global_model_id is None
        assert s.execute(select(GlobalModel)).scalars().all() == []


def test_load_active_model_path_filters_by_source_and_state(db) -> None:
    url, sessions = db
    with sessions() as s:
        s.add(
            GlobalModel(
                version="seed-model",
                path="/models/seed.pt",
                checksum_sha256="b" * 64,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.FEDERATED,
                metrics={},
                is_active=True,
            )
        )
        s.commit()

    p = _persistence(url)
    assert p.load_active_model_path() == "/models/seed.pt"

    with sessions() as s:
        s.add(
            GlobalModel(
                version="inactive-model",
                path="/models/inactive.pt",
                checksum_sha256="c" * 64,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.FEDERATED,
                metrics={},
                is_active=False,
            )
        )
        s.add(
            GlobalModel(
                version="centralized-model",
                path="/models/cl.pt",
                checksum_sha256="d" * 64,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.CENTRALIZED,
                metrics={},
                is_active=True,
            )
        )
        s.commit()

    assert p.load_active_model_path() == "/models/seed.pt"

    empty = FLPersistence(url, dataset_type="diabetes", total_clients=3)
    assert empty.load_active_model_path() is None


def test_activate_best_picks_highest_score_and_is_idempotent(db) -> None:
    url, sessions = db
    p = _persistence(url)
    # score = f1 + roc_auc - loss → 0.7, 1.7, 0.0 (distinct on purpose)
    p.register_round(
        round_number=1,
        metrics={"f1": 0.5, "roc_auc": 0.6, "loss": 0.4},
        artifact_version="score-a",
        artifact_path="/models/a.pt",
        artifact_checksum="e" * 64,
    )
    p.register_round(
        round_number=2,
        metrics={"f1": 0.9, "roc_auc": 0.9, "loss": 0.1},
        artifact_version="score-b",
        artifact_path="/models/b.pt",
        artifact_checksum="f" * 64,
    )
    p.register_round(
        round_number=3,
        metrics={"f1": 0.2, "roc_auc": 0.3, "loss": 0.5},
        artifact_version="score-c",
        artifact_path="/models/c.pt",
        artifact_checksum="g" * 64,
    )

    assert p.activate_best() == "score-b"
    with sessions() as s:
        active = s.execute(
            select(GlobalModel).where(GlobalModel.is_active.is_(True))
        ).scalars().all()
        assert [m.version for m in active] == ["score-b"]

    assert p.activate_best() == "score-b"

    empty = FLPersistence(url, dataset_type="diabetes", total_clients=3)
    assert empty.activate_best() is None


def test_load_initial_state_success_with_fallback_payload(tmp_path) -> None:
    model = create_model(9)
    payload = {
        "state_dict": model.state_dict(),
        "input_dim": 9,
        "preprocessing": {"type": "standardization", "means": [0.1] * 9, "scales": [2.0] * 9},
        # datetime is not weights_only-safe: forces the fallback loader branch.
        "created_at": datetime.now(UTC),
    }
    path = tmp_path / "model.pt"
    torch.save(payload, path)

    loaded = _load_initial_state(path, 9)
    assert loaded is not None
    arrays, preprocessing = loaded
    assert len(arrays) == len(model.state_dict())
    assert preprocessing["type"] == "standardization"
    assert preprocessing["means"] == [0.1] * 9


def test_load_initial_state_rejects_corrupt_file(tmp_path) -> None:
    path = tmp_path / "corrupt.pt"
    path.write_bytes(b"definitely not a torch archive")
    assert _load_initial_state(path, 9) is None


def test_load_initial_state_rejects_wrong_input_dim(tmp_path) -> None:
    model = create_model(4)
    path = tmp_path / "wrong_dim.pt"
    torch.save({"state_dict": model.state_dict(), "input_dim": 4}, path)
    assert _load_initial_state(path, 9) is None


def test_create_strategy_without_database_starts_fresh(tmp_path) -> None:
    config = FederatedLearningConfig(artifact_root=tmp_path / "artifacts")
    strategy = create_strategy(config)
    assert strategy.preprocessing["type"] == "identity"
    assert len(parameters_to_ndarrays(strategy.initial_parameters)) > 0
    assert not strategy.persistence.enabled


def test_create_strategy_falls_back_when_artifact_unusable(db, tmp_path) -> None:
    url, sessions = db
    corrupt = tmp_path / "corrupt.pt"
    corrupt.write_bytes(b"junk")
    with sessions() as s:
        s.add(
            GlobalModel(
                version="unusable-model",
                path=str(corrupt),
                checksum_sha256="h" * 64,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.FEDERATED,
                metrics={},
                is_active=True,
            )
        )
        s.commit()

    config = FederatedLearningConfig(database_url=url, artifact_root=tmp_path / "out")
    strategy = create_strategy(config)
    assert strategy.preprocessing["type"] == "identity"


def test_run_server_seeds_from_active_model_and_activates_best(db, tmp_path, monkeypatch) -> None:
    url, sessions = db

    model = create_model(9)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.network[-1].bias.fill_(2.0)
    registry = ModelRegistry(tmp_path / "artifacts")
    artifact = registry.save_global_model(
        parameters=get_model_parameters(model),
        input_dim=9,
        dataset_type=DatasetType.HEART_DISEASE,
        round_number=0,
        metrics={"accuracy": 0.8},
        preprocessing={
            "type": "standardization",
            "means": [0.1] * 9,
            "scales": [2.0] * 9,
        },
    )

    with sessions() as s:
        s.add(
            GlobalModel(
                version="bootstrap",
                path=str(artifact.path),
                checksum_sha256=artifact.checksum_sha256,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.FEDERATED,
                metrics={"accuracy": 0.8},
                is_active=True,
            )
        )
        s.commit()

    seeder = _persistence(url)
    seeder.register_round(
        round_number=1,
        metrics={"f1": 0.9, "roc_auc": 0.9, "loss": 0.1},
        artifact_version="run-r0001",
        artifact_path=str(tmp_path / "m1.pt"),
        artifact_checksum="1" * 64,
    )
    seeder.register_round(
        round_number=2,
        metrics={"f1": 0.4, "roc_auc": 0.5, "loss": 0.2},
        artifact_version="run-r0002",
        artifact_path=str(tmp_path / "m2.pt"),
        artifact_checksum="2" * 64,
    )

    captured: dict = {}

    def fake_start_server(**kwargs):
        captured.update(kwargs)
        return "history-sentinel"

    monkeypatch.setattr(fl.server, "start_server", fake_start_server)

    config = FederatedLearningConfig(
        database_url=url,
        rounds=1,
        artifact_root=tmp_path / "fl_out",
    )
    history = run_server(config)
    assert history == "history-sentinel"

    strategy = captured["strategy"]
    # Round 0 seeded from the active artifact, including its preprocessing spec.
    assert strategy.preprocessing["type"] == "standardization"
    assert strategy.preprocessing["means"] == [0.1] * 9
    initial = parameters_to_ndarrays(strategy.initial_parameters)
    assert float(initial[-1][0]) == pytest.approx(2.0)

    with sessions() as s:
        assert s.execute(select(TrainingRound)).scalars().all() == []
        active = s.execute(
            select(GlobalModel).where(GlobalModel.is_active.is_(True))
        ).scalars().all()
        assert [m.version for m in active] == ["run-r0001"]


def test_run_server_passes_mtls_certificates(db, tmp_path, monkeypatch) -> None:
    url, _ = db
    ca = tmp_path / "ca.crt"
    ca.write_bytes(b"CADATA")
    server_cert = tmp_path / "server.crt"
    server_cert.write_bytes(b"CERTDATA")
    server_key = tmp_path / "server.key"
    server_key.write_bytes(b"KEYDATA")

    captured: dict = {}
    monkeypatch.setattr(
        fl.server, "start_server", lambda **kwargs: captured.update(kwargs) or "history"
    )

    config = FederatedLearningConfig(
        database_url=url,
        rounds=1,
        artifact_root=tmp_path / "out",
        use_mtls=True,
        ca_cert_path=ca,
        server_cert_path=server_cert,
        server_key_path=server_key,
    )
    run_server(config)
    assert captured["certificates"] == (b"CADATA", b"CERTDATA", b"KEYDATA")


def test_run_server_rejects_mtls_without_certificate_paths(monkeypatch) -> None:
    def _boom(**_kwargs):
        raise AssertionError("start_server must not be called")

    monkeypatch.setattr(fl.server, "start_server", _boom)

    config = FederatedLearningConfig(use_mtls=True, ca_cert_path=None)
    with pytest.raises(ValueError, match="certificate paths"):
        run_server(config)


def test_parse_args_reads_cli_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--rounds", "3", "--dataset-type", "diabetes", "--lr", "0.01"],
    )
    args = parse_args()
    assert args.rounds == 3
    assert args.dataset_type == "diabetes"
    assert args.lr == pytest.approx(0.01)

    monkeypatch.setattr(sys, "argv", ["prog"])
    assert parse_args().rounds is None


def test_main_wires_cli_overrides_into_run_server(db, tmp_path, monkeypatch) -> None:
    url, _ = db
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(sys, "argv", ["prog", "--rounds", "2", "--clients", "2"])

    started: dict = {}
    monkeypatch.setattr(
        fl.server, "start_server", lambda **kwargs: started.update(kwargs) or "history"
    )

    assert main() is None
    assert started["config"].num_rounds == 2
    assert started["strategy"].config.rounds == 2
    assert started["strategy"].config.clients == 2
