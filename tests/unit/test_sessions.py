import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.auth.sessions import InMemorySessionStore, SessionData


@pytest.mark.asyncio
async def test_in_memory_session_lifecycle() -> None:
    store = InMemorySessionStore()
    session = SessionData(
        session_id="session-1",
        user_id=uuid.uuid4(),
        refresh_token_hash="hash-1",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    await store.create(session)
    stored = await store.get("session-1")
    assert stored is not None
    assert stored.refresh_token_hash == "hash-1"

    await store.rotate_refresh_token("session-1", "hash-2")
    rotated = await store.get("session-1")
    assert rotated is not None
    assert rotated.refresh_token_hash == "hash-2"

    await store.revoke("session-1")
    assert await store.get("session-1") is None
