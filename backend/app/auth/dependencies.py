"""FastAPI security dependencies."""

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.rbac import Permission, role_has_permission
from backend.app.auth.security import decode_token
from backend.app.auth.sessions import SessionStore
from backend.app.core.errors import AuthenticationError, AuthorizationError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
    session_store: SessionStore = Depends(get_session_store),
) -> User:
    settings = request.app.state.settings
    payload = decode_token(token, token_type="access", settings=settings)
    stored_session = await session_store.get(payload.sid)
    if stored_session is None or stored_session.user_id != payload.sub:
        raise AuthenticationError("Session is no longer active")
    user = await UserService.get_by_id(session, payload.sub)
    if user is None or not user.is_active:
        raise AuthenticationError("User account is inactive or unavailable")
    await session_store.touch(payload.sid)
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = set(roles)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise AuthorizationError()
        return current_user

    return dependency


def require_permissions(*permissions: Permission) -> Callable[[User], User]:
    required = set(permissions)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        missing = [
            permission.value
            for permission in required
            if not role_has_permission(current_user.role, permission)
        ]
        if missing:
            raise AuthorizationError(
                f"Missing required permissions: {', '.join(sorted(missing))}"
            )
        return current_user

    return dependency


def assert_same_hospital_or_system_admin(
    current_user: User,
    hospital_id: uuid.UUID,
    *,
    message: str = "Cross-hospital access is not allowed",
) -> None:
    if current_user.role == UserRole.SYSTEM_ADMIN:
        return
    if current_user.hospital_id != hospital_id:
        raise AuthorizationError(message)
