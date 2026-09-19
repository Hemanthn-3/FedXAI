"""User management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user, require_roles
from backend.app.core.errors import AuthorizationError, NotFoundError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.schemas.common import MessageResponse, Page, PaginationParams
from backend.app.schemas.user import PasswordChangeRequest, UserCreate, UserRead, UserUpdate
from backend.app.services.audit_service import AuditService
from backend.app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=Page[UserRead])
async def list_users(
    params: PaginationParams = Depends(),
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> Page[UserRead]:
    """List platform users. System-admin only."""

    users, total = await UserService.list(session, offset=params.offset, limit=params.limit)
    return Page(
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        offset=params.offset,
        limit=params.limit,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> UserRead:
    """Create a user in any supported role."""

    user = await UserService.create(session, payload)
    await AuditService.record(
        session,
        action="users.create",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={
            "role": user.role.value,
            "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        },
        request=request,
    )
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def read_own_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me/password", response_model=MessageResponse)
async def change_own_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    await UserService.change_password(session, current_user, payload)
    await AuditService.record(
        session,
        action="users.password_change",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        request=request,
    )
    return MessageResponse(message="Password changed successfully")


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserRead:
    """Read a user profile. Users can read themselves; admins can read all."""

    if current_user.role != UserRole.SYSTEM_ADMIN and current_user.id != user_id:
        raise AuthorizationError()
    user = await UserService.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("User")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> UserRead:
    """Update role, hospital membership, activation, or profile metadata."""

    user = await UserService.update(session, user_id, payload)
    await AuditService.record(
        session,
        action="users.update",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        details=payload.model_dump(exclude_unset=True, mode="json"),
        request=request,
    )
    return UserRead.model_validate(user)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Deactivate a user without deleting audit or clinical provenance."""

    if current_user.id == user_id:
        raise AuthorizationError("System administrators cannot deactivate their own account")
    user = await UserService.update(session, user_id, UserUpdate(is_active=False))
    await AuditService.record(
        session,
        action="users.deactivate",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    return MessageResponse(message="User deactivated successfully")
