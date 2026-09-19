"""Patient management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import assert_same_hospital_or_system_admin, require_roles
from backend.app.core.errors import AuthorizationError, NotFoundError
from backend.app.database import get_db_session
from backend.app.models.enums import UserRole
from backend.app.models.patient import Patient
from backend.app.models.user import User
from backend.app.schemas.common import MessageResponse, Page, PaginationParams
from backend.app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from backend.app.services.audit_service import AuditService
from backend.app.services.patient_service import PatientService

router = APIRouter()


def _resolve_patient_hospital(current_user: User, requested: uuid.UUID | None) -> uuid.UUID:
    if current_user.role == UserRole.SYSTEM_ADMIN:
        if requested is None:
            raise AuthorizationError("System administrators must provide hospital_id")
        return requested
    if current_user.hospital_id is None:
        raise AuthorizationError("User is not attached to a hospital")
    if requested is not None and requested != current_user.hospital_id:
        raise AuthorizationError("Cross-hospital patient creation is not allowed")
    return current_user.hospital_id


@router.get("", response_model=Page[PatientRead])
async def list_patients(
    params: PaginationParams = Depends(),
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> Page[PatientRead]:
    """List patients within the user's allowed hospital scope."""

    scoped_hospital_id = (
        None if current_user.role == UserRole.SYSTEM_ADMIN else current_user.hospital_id
    )
    if current_user.role != UserRole.SYSTEM_ADMIN and scoped_hospital_id is None:
        raise AuthorizationError("User is not attached to a hospital")
    patients, total = await PatientService.list(
        session,
        offset=params.offset,
        limit=params.limit,
        hospital_id=scoped_hospital_id,
    )
    return Page(
        items=[PatientRead.model_validate(patient) for patient in patients],
        total=total,
        offset=params.offset,
        limit=params.limit,
    )


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    request: Request,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PatientRead:
    """Create a canonical patient record for prediction and reporting."""

    hospital_id = _resolve_patient_hospital(current_user, payload.hospital_id)
    patient = await PatientService.create(session, payload, hospital_id=hospital_id)
    await AuditService.record(
        session,
        action="patients.create",
        user_id=current_user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        details={"hospital_id": str(patient.hospital_id)},
        request=request,
    )
    return PatientRead.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PatientRead:
    """Read a patient record within hospital scope."""

    patient = await PatientService.get_by_id(session, patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    return PatientRead.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    request: Request,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PatientRead:
    """Update clinical features used by prediction."""

    patient: Patient | None = await PatientService.get_by_id(session, patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    patient = await PatientService.update(session, patient_id, payload)
    await AuditService.record(
        session,
        action="patients.update",
        user_id=current_user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        details=payload.model_dump(exclude_unset=True, mode="json"),
        request=request,
    )
    return PatientRead.model_validate(patient)


@router.delete("/{patient_id}", response_model=MessageResponse)
async def delete_patient(
    patient_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(
        require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Delete a patient and any persisted predictions in the user's hospital scope."""

    patient = await PatientService.get_by_id(session, patient_id)
    if patient is None:
        raise NotFoundError("Patient")
    assert_same_hospital_or_system_admin(current_user, patient.hospital_id)
    deleted_patient = await PatientService.delete(session, patient_id)
    await AuditService.record(
        session,
        action="patients.delete",
        user_id=current_user.id,
        resource_type="patient",
        resource_id=str(deleted_patient.id),
        details={"hospital_id": str(deleted_patient.hospital_id)},
        request=request,
    )
    return MessageResponse(message="Patient deleted successfully")
