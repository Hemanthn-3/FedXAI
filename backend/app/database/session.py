"""Asynchronous database engine and request-scoped sessions.

Supports both PostgreSQL (production) and SQLite (testing) backends.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import get_settings

settings = get_settings()

# SQLite does not support connection pool configuration arguments.
# Use NullPool for SQLite and standard pool settings for PostgreSQL.
_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    from sqlalchemy.pool import NullPool  # type: ignore[attr-defined]
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
    )

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a transaction-safe session for a FastAPI dependency."""

    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_database() -> None:
    """Release the engine pool during application shutdown."""

    await engine.dispose()
