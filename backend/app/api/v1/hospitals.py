"""Hospital management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import (
    assert_same_hospital_or_system_admin,
    get_current_user,
    require_roles,
)
from backend.app.core.errors import AuthorizationError, NotFoundError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.hospital import Hospital
from backend.app.models.user import User
from backend.app.schemas.common import Page, PaginationParams
from backend.app.schemas.hospital import HospitalCreate, HospitalRead, HospitalUpdate
from backend.app.services.audit_service import AuditService
from backend.app.services.hospital_service import HospitalService

router = APIRouter()


@router.get("", response_model=Page[HospitalRead])
async def list_hospitals(
    params: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Page[HospitalRead]:
    """List all hospitals for system roles, or the current user's hospital."""

    if current_user.role in {UserRole.SYSTEM_ADMIN, UserRole.RESEARCHER}:
        scoped_hospital_id = None
    elif current_user.hospital_id is not None:
        scoped_hospital_id = current_user.hospital_id
    else:
        raise AuthorizationError()
    hospitals, total = await HospitalService.list(
        session,
        offset=params.offset,
        limit=params.limit,
        hospital_id=scoped_hospital_id,
    )
    return Page(
        items=[HospitalRead.model_validate(hospital) for hospital in hospitals],
        total=total,
        offset=params.offset,
        limit=params.limit,
    )


@router.post("", response_model=HospitalRead, status_code=status.HTTP_201_CREATED)
async def create_hospital(
    payload: HospitalCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> HospitalRead:
    """Register a hospital tenant and federated node ID."""

    hospital = await HospitalService.create(session, payload)
    await AuditService.record(
        session,
        action="hospitals.create",
        user_id=current_user.id,
        resource_type="hospital",
        resource_id=str(hospital.id),
        details={"node_id": hospital.node_id},
        request=request,
    )
    return HospitalRead.model_validate(hospital)


@router.get("/{hospital_id}", response_model=HospitalRead)
async def get_hospital(
    hospital_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> HospitalRead:
    """Read hospital details with tenant scoping."""

    if current_user.role not in {UserRole.SYSTEM_ADMIN, UserRole.RESEARCHER}:
        assert_same_hospital_or_system_admin(current_user, hospital_id)
    hospital = await HospitalService.get_by_id(session, hospital_id)
    if hospital is None:
        raise NotFoundError("Hospital")
    return HospitalRead.model_validate(hospital)


@router.patch("/{hospital_id}", response_model=HospitalRead)
async def update_hospital(
    hospital_id: uuid.UUID,
    payload: HospitalUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> HospitalRead:
    """Update hospital metadata or operational status."""

    hospital: Hospital = await HospitalService.update(session, hospital_id, payload)
    await AuditService.record(
        session,
        action="hospitals.update",
        user_id=current_user.id,
        resource_type="hospital",
        resource_id=str(hospital.id),
        details=payload.model_dump(exclude_unset=True, mode="json"),
        request=request,
    )
    return HospitalRead.model_validate(hospital)
