"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration shared by backend services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    app_name: str = "FedPedia-XAI"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    trusted_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "backend")

    database_url: str = (
        "postgresql+asyncpg://fedpedia:change-this-in-your-local-env"
        "@localhost:5432/fedpedia_xai"
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    session_backend: str = "redis"
    rate_limit_backend: str = "redis"
    auth_rate_limit_per_minute: int = Field(default=20, ge=1, le=600)

    jwt_secret_key: SecretStr = SecretStr("replace-with-a-long-random-access-secret")
    jwt_refresh_secret_key: SecretStr = SecretStr("replace-with-a-long-random-refresh-secret")
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "fedpedia-xai"
    jwt_audience: str = "fedpedia-xai-users"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    bootstrap_admin_enabled: bool = True

    artifact_root: Path = Path("artifacts")
    report_root: Path = Path("reports")

    # ── Patient PHI field-level encryption (AES-256-GCM) ────────────────────
    # Generate key: python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    patient_field_encryption_key: SecretStr = SecretStr("replace-with-32-byte-base64-encoded-key")

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized.startswith("/"):
            raise ValueError("API_V1_PREFIX must begin with '/'")
        return normalized

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_csv_tuple(cls, value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(value, str):
            stripped = value.strip()
            # Handle JSON-encoded lists: '["http://a", "http://b"]'
            if stripped.startswith("["):
                import json
                try:
                    parsed = json.loads(stripped)
                    return tuple(str(item).strip() for item in parsed if str(item).strip())
                except json.JSONDecodeError:
                    pass
            # Plain comma-separated string
            return tuple(item.strip() for item in stripped.split(",") if item.strip())
        return tuple(value)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not (value.startswith("postgresql+asyncpg://") or value.startswith("sqlite+aiosqlite://")):
            raise ValueError("DATABASE_URL must use either postgresql+asyncpg or sqlite+aiosqlite driver")
        return value

    @field_validator("session_backend", "rate_limit_backend")
    @classmethod
    def validate_backend_choice(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"redis", "memory"}:
            raise ValueError("backend must be either 'redis' or 'memory'")
        return normalized

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env.lower() == "production":
            insecure_values = {
                self.jwt_secret_key.get_secret_value(),
                self.jwt_refresh_secret_key.get_secret_value(),
            }
            if any(value.startswith("replace-with-") for value in insecure_values):
                raise ValueError("production JWT secrets must be explicitly randomized")

            # Validate encryption key decodes to exactly 32 bytes
            import base64
            enc_key_raw = self.patient_field_encryption_key.get_secret_value()
            if enc_key_raw.startswith("replace-with-"):
                raise ValueError("production PATIENT_FIELD_ENCRYPTION_KEY must be set")
            try:
                decoded = base64.urlsafe_b64decode(enc_key_raw + "==")
            except Exception as exc:
                raise ValueError("PATIENT_FIELD_ENCRYPTION_KEY is not valid base64") from exc
            if len(decoded) != 32:
                raise ValueError(
                    f"PATIENT_FIELD_ENCRYPTION_KEY must decode to 32 bytes (got {len(decoded)})"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide immutable settings instance."""

    return Settings()
