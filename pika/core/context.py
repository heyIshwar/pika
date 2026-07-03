"""Request-scoped context vars (tenant_id, trace_id, session/user/run ids)."""
from __future__ import annotations

import contextvars

_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_tenant_id", default=None
)
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_trace_id", default=None
)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_session_id", default=None
)
_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_user_id", default=None
)
_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pika_run_id", default=None
)


def get_tenant_id() -> str | None:
    return _tenant_id.get()


def set_tenant_id(tenant_id: str | None) -> contextvars.Token:
    return _tenant_id.set(tenant_id)


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(trace_id: str | None) -> contextvars.Token:
    return _trace_id.set(trace_id)


def get_session_id() -> str | None:
    return _session_id.get()


def set_session_id(session_id: str | None) -> contextvars.Token:
    return _session_id.set(session_id)


def get_user_id() -> str | None:
    return _user_id.get()


def set_user_id(user_id: str | None) -> contextvars.Token:
    return _user_id.set(user_id)


def get_run_id() -> str | None:
    return _run_id.get()


def set_run_id(run_id: str | None) -> contextvars.Token:
    return _run_id.set(run_id)
