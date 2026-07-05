"""Langfuse root observation wrapper for a single agent/chat turn."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pika.core.context import set_trace_id
from pika.observability.tracing import langfuse_enabled


@asynccontextmanager
async def langfuse_turn_context(
    *,
    name: str,
    input: Any,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> AsyncIterator[Any]:
    """
    Open a Langfuse agent observation for one turn and bind its trace_id.

    Yields the Langfuse observation object (or None when Langfuse is disabled).
    """
    if not langfuse_enabled():
        yield None
        return

    from langfuse import get_client, propagate_attributes

    lf = get_client()
    with lf.start_as_current_observation(
        as_type="agent",
        name=name,
        input=input,
    ) as turn_obs:
        with propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or None,
            tags=tags or None,
        ):
            set_trace_id(turn_obs.trace_id)
            try:
                yield turn_obs
            finally:
                set_trace_id(None)
        lf.flush()
