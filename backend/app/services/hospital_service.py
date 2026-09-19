"""Hospital tenant management service."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.models.hospital import Hospital
from backend.app.schemas.hospital import HospitalCreate, HospitalUpdate


class HospitalService:
    @staticmethod
    async def get_by_id(session: AsyncSession, hospital_id: uuid.UUID) -> Hospital | None:
        return await session.get(Hospital, hospital_id)

    @staticmethod
    async def get_by_node_id(session: AsyncSession, node_id: str) -> Hospital | None:
        result = await session.execute(select(Hospital).where(Hospital.node_id == node_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 50,
        hospital_id: uuid.UUID | None = None,
    ) -> tuple[list[Hospital], int]:
        filters = []
        if hospital_id is not None:
            filters.append(Hospital.id == hospital_id)
        total_stmt = select(func.count()).select_from(Hospital).where(*filters)
        total = int(await session.scalar(total_stmt) or 0)
        result = await session.execute(
            select(Hospital)
            .where(*filters)
            .order_by(Hospital.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def create(session: AsyncSession, payload: HospitalCreate) -> Hospital:
        existing_name = await session.scalar(
            select(Hospital.id).where(Hospital.name == payload.name)
        )
        existing_node = await session.scalar(
            select(Hospital.id).where(Hospital.node_id == payload.node_id)
        )
        if existing_name:
            raise ConflictError("Hospital name already exists", {"field": "name"})
        if existing_node:
            raise ConflictError("Hospital node_id already exists", {"field": "node_id"})
        hospital = Hospital(**payload.model_dump())
        session.add(hospital)
        await session.flush()
        await session.refresh(hospital)
        return hospital

    @staticmethod
    async def update(
        session: AsyncSession,
        hospital_id: uuid.UUID,
        payload: HospitalUpdate,
    ) -> Hospital:
        hospital = await HospitalService.get_by_id(session, hospital_id)
        if hospital is None:
            raise NotFoundError("Hospital")
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            existing = await session.scalar(
                select(Hospital.id).where(
                    Hospital.name == updates["name"],
                    Hospital.id != hospital_id,
                )
            )
            if existing:
                raise ConflictError("Hospital name already exists", {"field": "name"})
        for key, value in updates.items():
            setattr(hospital, key, value)
        await session.flush()
        await session.refresh(hospital)
        return hospital
