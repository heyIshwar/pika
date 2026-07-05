"""Pika API middleware: auth and tenant context."""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from pika.core.context import set_role, set_tenant_id, set_user_id


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate X-Pika-Key header when PIKA_API_KEY env var is set."""

    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("PIKA_API_KEY")
        if api_key:
            provided = request.headers.get("X-Pika-Key", "")
            if provided != api_key:
                if request.url.path != "/health":
                    return JSONResponse({"detail": "Invalid or missing X-Pika-Key"}, status_code=401)
        return await call_next(request)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extract request identity headers into ContextVars.

  Dev-only: X-User-ID and X-Role are trusted when PIKA_API_KEY is not set,
  or when a valid X-Pika-Key is provided. Production apps should register
  custom JWT middleware instead of trusting these headers.
    """

    async def dispatch(self, request: Request, call_next):
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
