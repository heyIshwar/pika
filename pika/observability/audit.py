"""Audit sink protocol for tool-call collection during agent turns."""
from __future__ import annotations

import contextvars
import logging
from typing import Callable

logger = logging.getLogger("pika.observability.audit")

AuditSink = Callable[[dict], None]

_tool_calls: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "pika_audit_tool_calls", default=None
)
_audit_sink: AuditSink | None = None


def set_audit_sink(sink: AuditSink | None) -> None:
    global _audit_sink
    _audit_sink = sink


def start_turn() -> None:
    _tool_calls.set([])


def tool_sink(entry: dict) -> None:
    calls = _tool_calls.get()
    if calls is not None:
        calls.append(entry)
    if _audit_sink is not None:
        try:
            _audit_sink(entry)
        except Exception:
            logger.exception("audit sink failed")


def collected_tool_calls() -> list:
    return list(_tool_calls.get() or [])
