"""Application exceptions and FastAPI error handlers."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base exception with a stable API error code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "application_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_failed",
        )


class AuthorizationError(AppError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="insufficient_permissions",
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            details=details,
        )


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            f"{resource} was not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
        )


def error_payload(
    *,
    code: str,
    message: str,
    request: Request,
    details: Any | None = None,
) -> dict[str, Any]:
    """Return a consistent JSON error envelope."""

    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=exc.code,
            message=exc.message,
            request=request,
            details=exc.details,
        ),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="http_error",
            message=str(exc.detail),
            request=request,
        ),
        headers=getattr(exc, "headers", None),
    )


def _clean_error_details(obj: Any) -> Any:
    """Recursively convert bytes objects in validation error details to string to prevent JSON serialization errors."""
    if isinstance(obj, dict):
        return {k: _clean_error_details(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_error_details(item) for item in obj]
    elif isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            code="validation_error",
            message="Request validation failed",
            request=request,
            details=_clean_error_details(exc.errors()),
        ),
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_payload(
            code="integrity_error",
            message="The request conflicts with existing data or database constraints",
            request=request,
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers used by the API."""

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)


ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]
