"""
Pika tracer — async context manager that writes spans to Agno's DB,
and optionally forwards to LangFuse or OpenTelemetry.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

from pika.core.context import (
    get_run_id,
    get_session_id,
    get_tenant_id,
    get_trace_id,
    get_user_id,
    set_run_id,
    set_session_id,
    set_trace_id,
    set_user_id,
)
from pika.observability.model import PikaSpan, SpanKind


def langfuse_enabled() -> bool:
    env = os.getenv("LANGFUSE_ENABLED", "").lower()
    if env == "true":
        return True
    if env == "false":
        return False
    try:
        from pika.config.loader import get_settings

        return bool(get_settings().get("observability", {}).get("langfuse_enabled", False))
    except Exception:
        return False


def langfuse_otel_active() -> bool:
    """True when Agno OpenInference OTLP export to Langfuse is installed."""
    try:
        from pika.observability.langfuse_otel import langfuse_otel_active as active

        return active()
    except ImportError:
        return False


def otel_enabled() -> bool:
    env = os.getenv("OTEL_ENABLED", "").lower()
    if env == "true":
        return True
    if env == "false":
        return False
    try:
        from pika.config.loader import get_settings

        return bool(get_settings().get("observability", {}).get("otel_enabled", False))
    except Exception:
        return False


class Tracer:
    """
    Per-component tracer.  Writes spans to Agno's DB and optionally to
    LangFuse / OpenTelemetry.  All spans for a single agent.run() share
    one trace_id stored in a ContextVar.
    """

    def __init__(self, component: str, db=None):
        self._component = component
        self._db = db
        use_lf_sdk = langfuse_enabled() and not langfuse_otel_active()
        self._lf = self._build_langfuse() if use_lf_sdk else None
        self._otel = self._build_otel() if otel_enabled() else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def run_context(
        self,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        run_id: str | None = None,
        extra_metadata: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        Start a traced agent run: set pika context vars and Langfuse trace attributes.

        Propagates user_id, session_id, run_id, and pika_trace_id to all child spans.
        Must wrap the whole run before any span() calls.
        """
        trace_id = get_trace_id() or str(uuid4())
        if get_trace_id() is None:
            set_trace_id(trace_id)
        set_session_id(session_id)
        set_user_id(user_id)
        set_run_id(run_id)

        lf_propagate = None
        if self._lf:
            try:
                from langfuse import propagate_attributes

                metadata = {
                    key: str(value)
                    for key, value in {
                        "pika_trace_id": trace_id,
                        "run_id": run_id,
                        "tenant_id": get_tenant_id(),
                        "agent_id": self._component,
                        **(extra_metadata or {}),
                    }.items()
                    if value is not None
                }
                lf_propagate = propagate_attributes(
                    user_id=user_id,
                    session_id=session_id,
                    metadata=metadata or None,
                    tags=[self._component],
                    trace_name=trace_id,
                )
                lf_propagate.__enter__()
            except Exception:
                lf_propagate = None

        try:
            yield trace_id
        finally:
            if lf_propagate:
                try:
                    lf_propagate.__exit__(None, None, None)
                except Exception:
                    pass
            if self._lf:
                try:
                    self._lf.flush()
                except Exception:
                    pass
            set_session_id(None)
            set_user_id(None)
            set_run_id(None)

    @asynccontextmanager
    async def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_STEP,
        input: Any = None,
        attributes: dict | None = None,
        observation_name: str | None = None,
    ) -> AsyncIterator[dict]:
        """
        Async context manager that records a span.

        Yields a mutable dict so callers can attach `output` or extra keys:
            async with tracer.span("cache.get", kind=SpanKind.TOOL_CALL) as s:
                s["output"] = result
        """
        trace_id = get_trace_id() or str(uuid4())
        set_trace_id(trace_id)

        span_id = str(uuid4())
        start = datetime.now(timezone.utc)
        lf_name = observation_name or f"{self._component}.{name}"
        span_data: dict = {
            "span_id": span_id,
            "trace_id": trace_id,
            "name": lf_name,
            "kind": kind,
            "input": input,
            "output": None,
            "status": "OK",
            "error": None,
            "attributes": {
                "agent_id": self._component,
                "tenant_id": get_tenant_id(),
                "session_id": get_session_id(),
                "user_id": get_user_id(),
                "run_id": get_run_id(),
                "pika_trace_id": trace_id,
                **(attributes or {}),
            },
        }

        lf_ctx = None
        if self._lf:
            try:
                kind = span_data.get("kind", SpanKind.AGENT_STEP)
                lf_ctx = self._lf.start_as_current_observation(
                    as_type=self._lf_observation_type(kind),
                    name=lf_name,
                    input=input,
                    metadata=span_data.get("attributes", {}),
                )
                lf_span = lf_ctx.__enter__()
            except Exception:
                lf_ctx = None
                lf_span = None
        else:
            lf_span = None

        otel_span = self._otel_start(span_data) if self._otel else None

        try:
            yield span_data
        except Exception as exc:
            span_data["status"] = "ERROR"
            span_data["error"] = str(exc)
            if lf_span:
                try:
                    lf_span.update(status_message=str(exc), level="ERROR")
                except Exception:
                    pass
            raise
        finally:
            end = datetime.now(timezone.utc)
            duration_ms = int((end - start).total_seconds() * 1000)
            pika_span = PikaSpan(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=None,
                name=span_data["name"],
                span_kind=kind.value if isinstance(kind, SpanKind) else str(kind),
                status_code=span_data["status"],
                status_message=span_data.get("error"),
                start_time=start,
                end_time=end,
                duration_ms=duration_ms,
                attributes={
                    **span_data["attributes"],
                    "input": str(input)[:500] if input is not None else None,
                    "output": str(span_data.get("output", ""))[:500],
                },
                created_at=datetime.now(timezone.utc),
            )
            if self._db:
                try:
                    self._db.create_span(pika_span)
                except Exception:
                    pass

            if lf_span:
                try:
                    lf_span.update(
                        output=span_data.get("output"),
                        status_message=span_data.get("error"),
                        level="ERROR" if span_data["status"] == "ERROR" else None,
                    )
                    if self._lf:
                        self._lf.flush()
                except Exception:
                    pass

            if lf_ctx:
                try:
                    lf_ctx.__exit__(None, None, None)
                except Exception:
                    pass

            if otel_span:
                try:
                    if span_data["status"] == "ERROR":
                        from opentelemetry.trace import StatusCode

                        otel_span.set_status(StatusCode.ERROR, span_data.get("error", ""))
                    otel_span.end()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # LangFuse helpers
    # ------------------------------------------------------------------

    def _build_langfuse(self):
        try:
            from langfuse import Langfuse

            return Langfuse()
        except Exception:
            return None

    def _lf_observation_type(self, kind: SpanKind | str) -> str:
        value = kind.value if isinstance(kind, SpanKind) else str(kind)
        if value in {SpanKind.TOOL_CALL.value, "tool_call"}:
            return "tool"
        if value in {SpanKind.AGENT_STEP.value, "agent_step"}:
            return "agent"
        return "span"

    # ------------------------------------------------------------------
    # OTEL helpers
    # ------------------------------------------------------------------

    def _build_otel(self):
        try:
            from opentelemetry import trace

            return trace.get_tracer(self._component)
        except Exception:
            return None

    def _otel_start(self, span_data: dict):
        try:
            return self._otel.start_span(span_data["name"])
        except Exception:
            return None


def get_tracer(component: str, db=None) -> Tracer:
    """Return a Tracer for the given component, wired to the current DB."""
    if db is None:
        try:
            from pika.infra.storage import get_storage

            db = get_storage()
        except Exception:
            pass
    return Tracer(component=component, db=db)
