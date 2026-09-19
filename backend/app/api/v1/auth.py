"""Authentication API endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user, get_session_store
from backend.app.auth.rate_limit import auth_rate_limit
from backend.app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_token_id,
    hash_token_id,
    secure_compare,
    token_expiry,
)
from backend.app.auth.sessions import SessionData, SessionStore
from backend.app.core.errors import AuthenticationError, AuthorizationError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPair,
)
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.user import UserCreate, UserRead
from backend.app.services.audit_service import AuditService
from backend.app.services.user_service import UserService

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")


async def _issue_token_pair(
    *,
    request: Request,
    user: User,
    session_store: SessionStore,
    existing_session_id: str | None = None,
    existing_expires_at: datetime | None = None,
) -> TokenPair:
    settings = request.app.state.settings
    session_id = existing_session_id or str(uuid.uuid4())
    refresh_token_id = generate_token_id()
    refresh_expires_at = existing_expires_at or token_expiry(
        days=settings.refresh_token_expire_days
    )
    refresh_hash = hash_token_id(refresh_token_id, settings)

    if existing_session_id is None:
        await session_store.create(
            SessionData(
                session_id=session_id,
                user_id=user.id,
                refresh_token_hash=refresh_hash,
                expires_at=refresh_expires_at,
                created_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
            )
        )
    else:
        await session_store.rotate_refresh_token(session_id, refresh_hash)

    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        role=user.role,
        session_id=session_id,
        hospital_id=user.hospital_id,
        settings=settings,
    )
    refresh_token, refresh_expires_at = create_refresh_token(
        user_id=user.id,
        role=user.role,
        session_id=session_id,
        refresh_token_id=refresh_token_id,
        hospital_id=user.hospital_id,
        settings=settings,
        expires_at=refresh_expires_at,
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=max(1, int((access_expires_at - datetime.now(UTC)).total_seconds())),
        refresh_expires_at=refresh_expires_at,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    session_store: SessionStore = Depends(get_session_store),
) -> AuthResponse:
    """Register a doctor/researcher, or bootstrap the first system admin."""

    user_count = await UserService.count_users(session)
    if payload.role == UserRole.SYSTEM_ADMIN:
        if not request.app.state.settings.bootstrap_admin_enabled or user_count > 0:
            raise AuthorizationError("System administrators must be created by an existing admin")
    elif payload.role == UserRole.HOSPITAL_ADMIN:
        raise AuthorizationError("Hospital administrators must be created by a system admin")

    user = await UserService.create(
        session,
        UserCreate(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            hospital_id=payload.hospital_id,
            is_active=True,
        ),
    )
    token_pair = await _issue_token_pair(request=request, user=user, session_store=session_store)
    await AuditService.record(
        session,
        action="auth.register",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"role": user.role.value},
        request=request,
    )
    return AuthResponse(**token_pair.model_dump(), user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(auth_rate_limit)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    session_store: SessionStore = Depends(get_session_store),
) -> AuthResponse:
    """Authenticate a user and create a refresh session."""

    try:
        user = await UserService.authenticate(
            session,
            email=str(payload.email),
            password=payload.password,
        )
    except AuthenticationError:
        await AuditService.record(
            session,
            action="auth.login_failed",
            details={"email": str(payload.email)},
            request=request,
        )
        await session.commit()
        raise
    token_pair = await _issue_token_pair(request=request, user=user, session_store=session_store)
    await AuditService.record(
        session,
        action="auth.login",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    return AuthResponse(**token_pair.model_dump(), user=UserRead.model_validate(user))


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(auth_rate_limit)],
)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    session_store: SessionStore = Depends(get_session_store),
) -> TokenPair:
    """Rotate a refresh token and issue a fresh access token."""

    settings = request.app.state.settings
    decoded = decode_token(payload.refresh_token, token_type="refresh", settings=settings)
    stored_session = await session_store.get(decoded.sid)
    if stored_session is None:
        raise AuthenticationError("Refresh session is no longer active")
    provided_hash = hash_token_id(decoded.jti, settings)
    if not secure_compare(provided_hash, stored_session.refresh_token_hash):
        await session_store.revoke(decoded.sid)
        raise AuthenticationError("Refresh token reuse was detected; session revoked")
    user = await UserService.get_by_id(session, decoded.sub)
    if user is None or not user.is_active:
        await session_store.revoke(decoded.sid)
        raise AuthenticationError("User account is inactive or unavailable")
    token_pair = await _issue_token_pair(
        request=request,
        user=user,
        session_store=session_store,
        existing_session_id=decoded.sid,
        existing_expires_at=stored_session.expires_at,
    )
    await AuditService.record(
        session,
        action="auth.refresh",
        user_id=user.id,
        resource_type="session",
        resource_id=decoded.sid,
        request=request,
    )
    return token_pair


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    session_store: SessionStore = Depends(get_session_store),
) -> MessageResponse:
    """Revoke the current refresh session."""

    decoded = decode_token(token, token_type="access", settings=request.app.state.settings)
    await session_store.revoke(decoded.sid)
    await AuditService.record(
        session,
        action="auth.logout",
        user_id=current_user.id,
        resource_type="session",
        resource_id=decoded.sid,
        request=request,
    )
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Return the current authenticated user."""

    return UserRead.model_validate(current_user)
