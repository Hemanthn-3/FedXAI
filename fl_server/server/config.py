"""Federated-learning runtime configuration."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fl_server.server.enums import AggregationStrategy, DatasetType


class FLSettings(BaseSettings):
    """Environment-backed Flower server and client settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    fl_server_address: str = "0.0.0.0:8080"
    fl_rounds: int = Field(default=20, ge=1, le=500)
    fl_clients: int = Field(default=3, ge=1, le=100)
    fl_epochs: int = Field(default=5, ge=1, le=200)
    fl_batch_size: int = Field(default=32, ge=1, le=4096)
    fl_lr: float = Field(default=0.001, gt=0, le=1)
    fl_aggregation_strategy: AggregationStrategy = AggregationStrategy.FEDAVG
    fl_dataset_type: DatasetType = DatasetType.HEART_DISEASE
    fl_artifact_root: Path = Path("artifacts/models")
    fl_test_size: float = Field(default=0.2, gt=0, lt=0.9)
    fl_random_state: int = 42

    # Database URL so the FL server can load the active global model and
    # register rounds.  Optional — persistence is skipped when unset.
    database_url: str | None = None

    # ── mTLS transport settings ─────────────────────────────────────────────
    fl_use_mtls: bool = False
    fl_ca_cert_path: Path | None = None
    fl_server_cert_path: Path | None = None
    fl_server_key_path: Path | None = None
    fl_client_cert_path: Path | None = None
    fl_client_key_path: Path | None = None

    # ── Differential Privacy settings ───────────────────────────────────────
    fl_dp_enabled: bool = False
    fl_dp_noise_scale: float = Field(default=1.0, gt=0)
    fl_dp_max_grad_norm: float = Field(default=1.0, gt=0)

    @field_validator("fl_server_address")
    @classmethod
    def validate_server_address(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("FL_SERVER_ADDRESS must include host:port")
        return value


@dataclass(frozen=True)
class FederatedLearningConfig:
    """Immutable configuration passed to FL runtime components."""

    server_address: str = "0.0.0.0:8080"
    rounds: int = 20
    clients: int = 3
    epochs: int = 5
    batch_size: int = 32
    lr: float = 0.001
    aggregation_strategy: AggregationStrategy = AggregationStrategy.FEDAVG
    dataset_type: DatasetType = DatasetType.HEART_DISEASE
    artifact_root: Path = Path("artifacts/models")
    test_size: float = 0.2
    random_state: int = 42
    database_url: str | None = None

    # ── mTLS transport settings ─────────────────────────────────────────────
    use_mtls: bool = False
    ca_cert_path: Path | None = None
    server_cert_path: Path | None = None
    server_key_path: Path | None = None
    client_cert_path: Path | None = None
    client_key_path: Path | None = None

    # ── Differential Privacy settings ───────────────────────────────────────
    dp_enabled: bool = False
    dp_noise_scale: float = 1.0
    dp_max_grad_norm: float = 1.0

    @classmethod
    def from_settings(cls, settings: FLSettings | None = None) -> "FederatedLearningConfig":
        resolved = settings or FLSettings()
        return cls(
            server_address=resolved.fl_server_address,
            rounds=resolved.fl_rounds,
            clients=resolved.fl_clients,
            epochs=resolved.fl_epochs,
            batch_size=resolved.fl_batch_size,
            lr=resolved.fl_lr,
            aggregation_strategy=resolved.fl_aggregation_strategy,
            dataset_type=resolved.fl_dataset_type,
            artifact_root=resolved.fl_artifact_root,
            test_size=resolved.fl_test_size,
            random_state=resolved.fl_random_state,
            database_url=resolved.database_url,
            # mTLS
            use_mtls=resolved.fl_use_mtls,
            ca_cert_path=resolved.fl_ca_cert_path,
            server_cert_path=resolved.fl_server_cert_path,
            server_key_path=resolved.fl_server_key_path,
            client_cert_path=resolved.fl_client_cert_path,
            client_key_path=resolved.fl_client_key_path,
            # Differential Privacy
            dp_enabled=resolved.fl_dp_enabled,
            dp_noise_scale=resolved.fl_dp_noise_scale,
            dp_max_grad_norm=resolved.fl_dp_max_grad_norm,
        )

    def fit_config(self) -> dict[str, str | int | float]:
        """Return serializable config sent to Flower clients each round."""

        return {
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "lr": self.lr,
            "dataset_type": self.dataset_type.value,
            "random_state": self.random_state,
        }
