"""Pika API middleware: auth and tenant context."""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from pika.core.context import set_tenant_id, set_trace_id


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate X-Pika-Key header when PIKA_API_KEY env var is set."""

    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("PIKA_API_KEY")
        if api_key:
            provided = request.headers.get("X-Pika-Key", "")
            if provided != api_key:
                # Allow /health unauthenticated
                if request.url.path != "/health":
                    return JSONResponse({"detail": "Invalid or missing X-Pika-Key"}, status_code=401)
        return await call_next(request)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract X-Tenant-ID into a ContextVar for downstream use."""

    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        token = set_tenant_id(tenant_id)
        try:
            return await call_next(request)
        finally:
            set_tenant_id(None)
