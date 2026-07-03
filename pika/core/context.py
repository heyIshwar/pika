"""Request-scoped context vars (tenant_id, trace_id)."""
from __future__ import annotations

import contextvars

_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_tenant_id", default=None
)
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_trace_id", default=None
)


def get_tenant_id() -> str | None:
    return _tenant_id.get()


def set_tenant_id(tenant_id: str | None) -> contextvars.Token:
    return _tenant_id.set(tenant_id)


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(trace_id: str | None) -> contextvars.Token:
    return _trace_id.set(trace_id)
