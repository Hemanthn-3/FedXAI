"""Password hashing and JWT token helpers."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.auth.rbac import permissions_for_role
from backend.app.core.config import Settings
from backend.app.core.errors import AuthenticationError
from backend.app.models.enums import UserRole
from backend.app.schemas.auth import TokenPayload

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password with the current recommended Argon2 profile."""

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""

    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def generate_token_id() -> str:
    """Generate an opaque token identifier suitable for refresh rotation."""

    return secrets.token_urlsafe(32)


def hash_token_id(token_id: str, settings: Settings) -> str:
    """Hash refresh-token IDs before storing them in Redis."""

    return hmac.new(
        settings.jwt_refresh_secret_key.get_secret_value().encode("utf-8"),
        token_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def token_expiry(minutes: int = 0, days: int = 0) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes, days=days)


def _base_claims(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    session_id: str,
    token_id: str,
    hospital_id: uuid.UUID | None,
    token_type: str,
    expires_at: datetime,
    settings: Settings,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "sub": str(user_id),
        "typ": token_type,
        "role": role.value,
        "sid": session_id,
        "jti": token_id,
        "permissions": permissions_for_role(role),
        "hospital_id": str(hospital_id) if hospital_id else None,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    session_id: str,
    hospital_id: uuid.UUID | None,
    settings: Settings,
) -> tuple[str, datetime]:
    """Create a signed access token."""

    expires_at = token_expiry(minutes=settings.access_token_expire_minutes)
    token_id = generate_token_id()
    payload = _base_claims(
        user_id=user_id,
        role=role,
        session_id=session_id,
        token_id=token_id,
        hospital_id=hospital_id,
        token_type="access",
        expires_at=expires_at,
        settings=settings,
    )
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    session_id: str,
    refresh_token_id: str,
    hospital_id: uuid.UUID | None,
    settings: Settings,
    expires_at: datetime | None = None,
) -> tuple[str, datetime]:
    """Create a signed refresh token."""

    expires_at = expires_at or token_expiry(days=settings.refresh_token_expire_days)
    payload = _base_claims(
        user_id=user_id,
        role=role,
        session_id=session_id,
        token_id=refresh_token_id,
        hospital_id=hospital_id,
        token_type="refresh",
        expires_at=expires_at,
        settings=settings,
    )
    token = jwt.encode(
        payload,
        settings.jwt_refresh_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_token(token: str, *, token_type: str, settings: Settings) -> TokenPayload:
    """Decode and validate a JWT access or refresh token."""

    secret = (
        settings.jwt_secret_key.get_secret_value()
        if token_type == "access"
        else settings.jwt_refresh_secret_key.get_secret_value()
    )
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        parsed = TokenPayload.model_validate(payload)
    except (InvalidTokenError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc
    if parsed.typ != token_type:
        raise AuthenticationError("Token type is not valid for this operation")
    return parsed


def secure_compare(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)
