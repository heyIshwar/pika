"""Attach metadata to the active Langfuse observation."""
from __future__ import annotations

import logging

logger = logging.getLogger("pika.observability.langfuse_metadata")


def enrich_current_trace(metadata: dict) -> None:
    """Merge metadata onto the current Langfuse span when tracing is enabled."""
    from pika.observability.tracing import langfuse_enabled

    if not langfuse_enabled() or not metadata:
        return

    try:
        from langfuse import get_client

        get_client().update_current_span(metadata=metadata)
    except Exception:
        logger.exception("failed to enrich Langfuse trace metadata")
