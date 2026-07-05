"""User feedback scores in Langfuse."""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger("pika.observability.feedback")

Rating = Literal["up", "down"]


def submit_langfuse_feedback(
    *,
    trace_id: str,
    rating: Rating,
    comment: str | None = None,
    metadata: dict | None = None,
    score_name: str = "user_feedback",
) -> bool:
    from pika.observability.tracing import langfuse_enabled

    if not langfuse_enabled() or not trace_id:
        return False
    try:
        from langfuse import Langfuse

        lf = Langfuse()
        lf.create_score(
            trace_id=trace_id,
            name=score_name,
            value=1.0 if rating == "up" else 0.0,
            comment=comment,
            metadata=metadata or None,
        )
        lf.flush()
        return True
    except Exception:
        logger.exception("langfuse feedback score failed")
        return False
