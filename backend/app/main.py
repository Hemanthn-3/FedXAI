"""FastAPI application factory for FedPedia-XAI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.router import api_router
from backend.app.auth.rate_limit import InMemoryRateLimiter, RedisRateLimiter
from backend.app.auth.sessions import InMemorySessionStore, RedisSessionStore
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import register_error_handlers
from backend.app.core.middleware import request_context_middleware
from backend.app.database.session import close_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.session_store = (
        RedisSessionStore(settings.redis_url, ttl_days=settings.refresh_token_expire_days)
        if settings.session_backend == "redis"
        else InMemorySessionStore()
    )
    app.state.rate_limiter = (
        RedisRateLimiter(settings.redis_url)
        if settings.rate_limit_backend == "redis"
        else InMemoryRateLimiter()
    )
    try:
        yield
    finally:
        await app.state.session_store.close()
        await app.state.rate_limiter.close()
        await close_database()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the API application."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        description=(
            "Privacy-preserving federated healthcare prediction platform with "
            "role-based access, hospital tenancy, and explainable AI provenance."
        ),
        version="0.1.0",
        debug=resolved_settings.app_debug,
        lifespan=lifespan,
        openapi_url=f"{resolved_settings.api_v1_prefix}/openapi.json",
        docs_url=f"{resolved_settings.api_v1_prefix}/docs",
        redoc_url=f"{resolved_settings.api_v1_prefix}/redoc",
    )
    app.state.settings = resolved_settings

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(resolved_settings.trusted_hosts))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
