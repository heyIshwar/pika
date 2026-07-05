"""Tracer behavior when Langfuse OTEL is active."""
import asyncio
from unittest.mock import MagicMock, patch

from pika.observability.tracing import Tracer


def test_tracer_skips_langfuse_sdk_when_otel_active():
    with patch("pika.observability.tracing.langfuse_otel_active", return_value=True):
        with patch("pika.observability.tracing.langfuse_enabled", return_value=True):
            tracer = Tracer("getting_started", db=MagicMock())
            assert tracer._lf is None


def test_tracer_uses_langfuse_sdk_when_otel_inactive():
    mock_lf = MagicMock()
    with patch("pika.observability.tracing.langfuse_otel_active", return_value=False):
        with patch("pika.observability.tracing.langfuse_enabled", return_value=True):
            with patch.object(Tracer, "_build_langfuse", return_value=mock_lf):
                tracer = Tracer("getting_started", db=MagicMock())
                assert tracer._lf is mock_lf


def test_run_context_preserves_existing_trace_id():
    from pika.core.context import get_trace_id, set_trace_id

    preset = "abc123def4567890abc123def4567890"
    set_trace_id(preset)
    try:
        with patch("pika.observability.tracing.langfuse_otel_active", return_value=True):
            with patch("pika.observability.tracing.langfuse_enabled", return_value=True):
                tracer = Tracer("getting_started", db=MagicMock())

                async def _run():
                    async with tracer.run_context(session_id="s1", user_id="u1") as tid:
                        assert tid == preset
                        assert get_trace_id() == preset

                asyncio.run(_run())
    finally:
        set_trace_id(None)
