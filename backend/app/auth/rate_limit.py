"""Rate limiting for sensitive API endpoints."""

import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from redis.asyncio import Redis

from backend.app.core.errors import AppError


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> None: ...

    async def close(self) -> None: ...


@dataclass
class _Counter:
    count: int
    reset_at: float


class InMemoryRateLimiter:
    """Process-local fixed-window rate limiter."""

    def __init__(self) -> None:
        self._counters: dict[str, _Counter] = {}

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.time()
        counter = self._counters.get(key)
        if counter is None or counter.reset_at <= now:
            self._counters[key] = _Counter(count=1, reset_at=now + window_seconds)
            return
        counter.count += 1
        if counter.count > limit:
            raise AppError(
                "Too many attempts. Please try again later.",
                status_code=429,
                code="rate_limit_exceeded",
                details={"retry_after_seconds": max(1, int(counter.reset_at - now))},
            )

    async def close(self) -> None:
        self._counters.clear()


class RedisRateLimiter:
    """Redis-backed fixed-window rate limiter."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        if count > limit:
            ttl = await self._redis.ttl(key)
            raise AppError(
                "Too many attempts. Please try again later.",
                status_code=429,
                code="rate_limit_exceeded",
                details={"retry_after_seconds": max(1, int(ttl))},
            )

    async def close(self) -> None:
        await self._redis.aclose()


async def auth_rate_limit(request: Request) -> None:
    """Apply IP+route throttling to authentication endpoints."""

    settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    client = request.client.host if request.client else "unknown"
    key = f"rate:auth:{client}:{request.url.path}"
    await limiter.check(key, limit=settings.auth_rate_limit_per_minute, window_seconds=60)
