"""User management and authentication lookup service."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.security import hash_password, verify_password
from backend.app.core.errors import AuthenticationError, ConflictError, NotFoundError
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.schemas.user import PasswordChangeRequest, UserCreate, UserUpdate
from backend.app.services.hospital_service import HospitalService


class UserService:
    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await session.get(User, user_id)

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    @staticmethod
    async def count_users(session: AsyncSession) -> int:
        return int(await session.scalar(select(func.count()).select_from(User)) or 0)

    @staticmethod
    async def has_system_admin(session: AsyncSession) -> bool:
        return bool(await session.scalar(select(User.id).where(User.role == UserRole.SYSTEM_ADMIN)))

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 50,
        hospital_id: uuid.UUID | None = None,
    ) -> tuple[list[User], int]:
        filters = []
        if hospital_id is not None:
            filters.append(User.hospital_id == hospital_id)
        total = int(
            await session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
        )
        result = await session.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def create(session: AsyncSession, payload: UserCreate) -> User:
        existing = await UserService.get_by_email(session, str(payload.email))
        if existing:
            raise ConflictError("Email is already registered", {"field": "email"})
        if payload.hospital_id is not None:
            hospital = await HospitalService.get_by_id(session, payload.hospital_id)
            if hospital is None:
                raise NotFoundError("Hospital")
        user = User(
            name=payload.name.strip(),
            email=str(payload.email).lower(),
            password_hash=hash_password(payload.password),
            role=payload.role,
            hospital_id=payload.hospital_id,
            is_active=payload.is_active,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
        user = await UserService.get_by_email(session, email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        return user

    @staticmethod
    async def update(session: AsyncSession, user_id: uuid.UUID, payload: UserUpdate) -> User:
        user = await UserService.get_by_id(session, user_id)
        if user is None:
            raise NotFoundError("User")
        updates = payload.model_dump(exclude_unset=True)
        hospital_id = updates.get("hospital_id")
        if hospital_id is not None:
            hospital = await HospitalService.get_by_id(session, hospital_id)
            if hospital is None:
                raise NotFoundError("Hospital")
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        for key, value in updates.items():
            setattr(user, key, value)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user: User,
        payload: PasswordChangeRequest,
    ) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        user.password_hash = hash_password(payload.new_password)
        await session.flush()
