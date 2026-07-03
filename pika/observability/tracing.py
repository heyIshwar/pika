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

from pika.core.context import get_tenant_id, get_trace_id, set_trace_id
from pika.observability.model import PikaSpan, SpanKind

LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"


class Tracer:
    """
    Per-component tracer.  Writes spans to Agno's DB and optionally to
    LangFuse / OpenTelemetry.  All spans for a single agent.run() share
    one trace_id stored in a ContextVar.
    """

    def __init__(self, component: str, db=None):
        self._component = component
        self._db = db
        self._lf = self._build_langfuse() if LANGFUSE_ENABLED else None
        self._otel = self._build_otel() if OTEL_ENABLED else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_STEP,
        input: Any = None,
        attributes: dict | None = None,
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
        span_data: dict = {
            "span_id": span_id,
            "trace_id": trace_id,
            "name": f"{self._component}.{name}",
            "kind": kind,
            "input": input,
            "output": None,
            "status": "OK",
            "error": None,
            "attributes": {
                "agent_id": self._component,
                "tenant_id": get_tenant_id(),
                **(attributes or {}),
            },
        }

        lf_span = self._lf_start(span_data) if self._lf else None
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
                        end_time=end,
                    )
                    if self._lf:
                        self._lf.flush()
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

    def _lf_start(self, span_data: dict):
        try:
            return self._lf.span(
                name=span_data["name"],
                input=span_data.get("input"),
                metadata=span_data.get("attributes", {}),
            )
        except Exception:
            return None

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
