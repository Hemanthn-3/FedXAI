import uuid

from backend.app.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    hash_token_id,
    secure_compare,
    verify_password,
)
from backend.app.core.config import Settings
from backend.app.models.enums import UserRole


def test_password_hashing_uses_non_plaintext_verifiable_hash() -> None:
    password = "VeryStrongPassword123!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_round_trip_contains_role_and_permissions() -> None:
    settings = Settings(
        session_backend="memory",
        rate_limit_backend="memory",
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    user_id = uuid.uuid4()

    token, _ = create_access_token(
        user_id=user_id,
        role=UserRole.DOCTOR,
        session_id="session-1",
        hospital_id=None,
        settings=settings,
    )
    payload = decode_token(token, token_type="access", settings=settings)

    assert payload.sub == user_id
    assert payload.role == UserRole.DOCTOR
    assert "patients:view" in payload.permissions


def test_refresh_token_hashing_is_stable_and_secret_bound() -> None:
    settings = Settings(
        session_backend="memory",
        rate_limit_backend="memory",
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )

    first = hash_token_id("refresh-id", settings)
    second = hash_token_id("refresh-id", settings)

    assert secure_compare(first, second)
    assert len(first) == 64
