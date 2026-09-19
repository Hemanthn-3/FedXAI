"""Patient management service with hospital scoping."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.models.patient import Patient
from backend.app.models.prediction import Prediction
from backend.app.schemas.patient import PatientCreate, PatientUpdate
from backend.app.services.hospital_service import HospitalService


class PatientService:
    @staticmethod
    async def get_by_id(session: AsyncSession, patient_id: uuid.UUID) -> Patient | None:
        return await session.get(Patient, patient_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 50,
        hospital_id: uuid.UUID | None = None,
    ) -> tuple[list[Patient], int]:
        filters = []
        if hospital_id is not None:
            filters.append(Patient.hospital_id == hospital_id)
        total = int(
            await session.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
        )
        result = await session.execute(
            select(Patient)
            .where(*filters)
            .order_by(Patient.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def create(
        session: AsyncSession,
        payload: PatientCreate,
        *,
        hospital_id: uuid.UUID,
    ) -> Patient:
        hospital = await HospitalService.get_by_id(session, hospital_id)
        if hospital is None:
            raise NotFoundError("Hospital")
        if payload.external_reference:
            existing = await session.scalar(
                select(Patient.id).where(
                    Patient.hospital_id == hospital_id,
                    Patient.external_reference == payload.external_reference,
                )
            )
            if existing:
                raise ConflictError(
                    "Patient external_reference already exists in this hospital",
                    {"field": "external_reference"},
                )
        values = payload.model_dump(exclude={"hospital_id"})
        patient = Patient(hospital_id=hospital_id, **values)
        session.add(patient)
        await session.flush()
        await session.refresh(patient)
        return patient

    @staticmethod
    async def update(
        session: AsyncSession,
        patient_id: uuid.UUID,
        payload: PatientUpdate,
    ) -> Patient:
        patient = await PatientService.get_by_id(session, patient_id)
        if patient is None:
            raise NotFoundError("Patient")
        updates = payload.model_dump(exclude_unset=True)
        external_reference = updates.get("external_reference")
        if external_reference:
            existing = await session.scalar(
                select(Patient.id).where(
                    Patient.hospital_id == patient.hospital_id,
                    Patient.external_reference == external_reference,
                    Patient.id != patient_id,
                )
            )
            if existing:
                raise ConflictError(
                    "Patient external_reference already exists in this hospital",
                    {"field": "external_reference"},
                )
        for key, value in updates.items():
            setattr(patient, key, value)
        await session.flush()
        await session.refresh(patient)
        return patient

    @staticmethod
    async def delete(session: AsyncSession, patient_id: uuid.UUID) -> Patient:
        patient = await PatientService.get_by_id(session, patient_id)
        if patient is None:
            raise NotFoundError("Patient")
        result = await session.execute(select(Prediction).where(Prediction.patient_id == patient_id))
        for prediction in result.scalars().all():
            await session.delete(prediction)
        await session.delete(patient)
        await session.flush()
        return patient
