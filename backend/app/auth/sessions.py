"""Refresh-session stores backed by Redis or memory."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import BaseModel
from redis.asyncio import Redis


class SessionData(BaseModel):
    session_id: str
    user_id: uuid.UUID
    refresh_token_hash: str
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None


class SessionStore(Protocol):
    async def create(self, session: SessionData) -> None: ...

    async def get(self, session_id: str) -> SessionData | None: ...

    async def rotate_refresh_token(self, session_id: str, refresh_token_hash: str) -> None: ...

    async def touch(self, session_id: str) -> None: ...

    async def revoke(self, session_id: str) -> None: ...

    async def close(self) -> None: ...


class InMemorySessionStore:
    """Process-local session store for tests and single-process development."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    async def create(self, session: SessionData) -> None:
        self._sessions[session.session_id] = session

    async def get(self, session_id: str) -> SessionData | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at <= datetime.now(UTC):
            self._sessions.pop(session_id, None)
            return None
        return session

    async def rotate_refresh_token(self, session_id: str, refresh_token_hash: str) -> None:
        session = await self.get(session_id)
        if session is not None:
            self._sessions[session_id] = session.model_copy(
                update={
                    "refresh_token_hash": refresh_token_hash,
                    "last_seen_at": datetime.now(UTC),
                }
            )

    async def touch(self, session_id: str) -> None:
        session = await self.get(session_id)
        if session is not None:
            self._sessions[session_id] = session.model_copy(
                update={"last_seen_at": datetime.now(UTC)}
            )

    async def revoke(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def close(self) -> None:
        self._sessions.clear()


class RedisSessionStore:
    """Redis-backed refresh-token session store."""

    def __init__(self, redis_url: str, *, ttl_days: int) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._ttl = int(timedelta(days=ttl_days).total_seconds())

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"auth:session:{session_id}"

    async def create(self, session: SessionData) -> None:
        await self._redis.setex(
            self._session_key(session.session_id),
            self._ttl,
            session.model_dump_json(),
        )

    async def get(self, session_id: str) -> SessionData | None:
        raw = await self._redis.get(self._session_key(session_id))
        if raw is None:
            return None
        session = SessionData.model_validate_json(raw)
        if session.expires_at <= datetime.now(UTC):
            await self.revoke(session_id)
            return None
        return session

    async def rotate_refresh_token(self, session_id: str, refresh_token_hash: str) -> None:
        session = await self.get(session_id)
        if session is None:
            return
        updated = session.model_copy(
            update={
                "refresh_token_hash": refresh_token_hash,
                "last_seen_at": datetime.now(UTC),
            }
        )
        await self._redis.setex(self._session_key(session_id), self._ttl, updated.model_dump_json())

    async def touch(self, session_id: str) -> None:
        session = await self.get(session_id)
        if session is None:
            return
        updated = session.model_copy(update={"last_seen_at": datetime.now(UTC)})
        await self._redis.setex(self._session_key(session_id), self._ttl, updated.model_dump_json())

    async def revoke(self, session_id: str) -> None:
        await self._redis.delete(self._session_key(session_id))

    async def close(self) -> None:
        await self._redis.aclose()
