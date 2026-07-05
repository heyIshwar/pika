"""Langfuse OTLP + Agno OpenInference instrumentation.

When LANGFUSE_ENABLED=true, instruments Agno agent runs (LLM generations,
tool calls) and exports nested spans to Langfuse via OTLP HTTP.
See: https://docs.agno.com/observability/langfuse
"""
from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger("pika.observability.langfuse_otel")

DEFAULT_OTEL_ENDPOINT = "https://cloud.langfuse.com/api/public/otel"

_installed = False
_otel_active = False


def langfuse_otel_active() -> bool:
    return _otel_active


def install_langfuse_otel() -> bool:
    """Idempotent — call once at app startup. Returns True if OTEL export is live."""
    global _installed, _otel_active
    if _installed:
        return _otel_active

    _installed = True

    from pika.observability.tracing import langfuse_enabled

    if not langfuse_enabled():
        return False

    public = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not public or not secret:
        logger.warning(
            "LANGFUSE_ENABLED but LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY missing — "
            "skipping Agno OTEL export"
        )
        return False

    try:
        from openinference.instrumentation.agno import AgnoInstrumentor
        from opentelemetry import trace as trace_api
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ImportError as exc:
        logger.warning(
            "Langfuse OTEL deps missing (%s) — pip install pika-agents[langfuse]",
            exc,
        )
        return False

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = DEFAULT_OTEL_ENDPOINT

    if not os.environ.get("OTEL_EXPORTER_OTLP_HEADERS"):
        auth = base64.b64encode(f"{public}:{secret}".encode()).decode()
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    trace_api.set_tracer_provider(tracer_provider=provider)
    AgnoInstrumentor().instrument(tracer_provider=provider)

    _otel_active = True
    logger.info(
        "Langfuse OTEL + AgnoInstrumentor active (endpoint=%s)",
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    return True
