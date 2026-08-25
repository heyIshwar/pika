"""Pika API middleware: auth and tenant context."""
from __future__ import annotations

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from pika.core.context import set_role, set_tenant_id, set_user_id

logger = logging.getLogger(__name__)

_HEALTH_PATHS = frozenset({"/health", "/healthz"})


def is_production() -> bool:
    """True when running with a production-style env indicator (PIKA_ENV)."""
    return os.getenv("PIKA_ENV", "development").strip().lower() in {
        "production",
        "prod",
    }


def _trust_identity_headers() -> bool:
    """Whether to accept X-Tenant-ID / X-User-ID / X-Role from the client.

    Default: true in non-prod, false in production (prefer verified JWT later).
    Override with PIKA_TRUST_IDENTITY_HEADERS=true|false.
    """
    raw = os.getenv("PIKA_TRUST_IDENTITY_HEADERS")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return not is_production()


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate X-Pika-Key when PIKA_API_KEY is set; fail closed in production."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        api_key = os.getenv("PIKA_API_KEY") or ""
        if not api_key:
            if is_production():
                logger.error(
                    "PIKA_API_KEY unset while PIKA_ENV=production — rejecting request"
                )
                return JSONResponse(
                    {
                        "detail": (
                            "Authentication required: set PIKA_API_KEY before serving "
                            "in production"
                        )
                    },
                    status_code=503,
                )
            return await call_next(request)

        provided = request.headers.get("X-Pika-Key", "")
        if not hmac.compare_digest(provided, api_key):
            return JSONResponse(
                {"detail": "Invalid or missing X-Pika-Key"},
                status_code=401,
            )
        return await call_next(request)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extract request identity headers into ContextVars when trusted.

    Production default: headers ignored unless PIKA_TRUST_IDENTITY_HEADERS=true
    (or a future JWT middleware sets context). Dev: headers trusted for local REPL/API.
    """

    async def dispatch(self, request: Request, call_next):
        tenant_id = user_id = role = None
        if _trust_identity_headers():
            tenant_id = request.headers.get("X-Tenant-ID")
            user_id = request.headers.get("X-User-ID")
            role = request.headers.get("X-Role")

        set_tenant_id(tenant_id)
        set_user_id(user_id)
        set_role(role)
        try:
            return await call_next(request)
        finally:
            set_tenant_id(None)
            set_user_id(None)
            set_role(None)
