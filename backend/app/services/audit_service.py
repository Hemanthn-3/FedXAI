"""Audit logging service."""

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit_log import AuditLog


class AuditService:
    """Create append-only audit events."""

    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        client_host = request.client.host if request and request.client else None
        user_agent = request.headers.get("User-Agent") if request else None
        audit = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=client_host,
            user_agent=user_agent[:512] if user_agent else None,
        )
        session.add(audit)
        await session.flush()
        return audit
