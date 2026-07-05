"""Langfuse metadata bridge."""
from unittest.mock import MagicMock, patch


def test_enrich_current_trace_updates_span():
    mock_lf = MagicMock()
    with patch("pika.observability.tracing.langfuse_enabled", return_value=True):
        with patch("langfuse.get_client", return_value=mock_lf):
            from pika.observability.langfuse_metadata import enrich_current_trace

            enrich_current_trace({"turn_id": "t1", "duration_ms": 42})
    mock_lf.update_current_span.assert_called_once()


def test_enrich_current_trace_noop_when_disabled():
    mock_lf = MagicMock()
    with patch("pika.observability.tracing.langfuse_enabled", return_value=False):
        with patch("langfuse.get_client", return_value=mock_lf):
            from pika.observability.langfuse_metadata import enrich_current_trace

            enrich_current_trace({"turn_id": "t1"})
    mock_lf.update_current_span.assert_not_called()
