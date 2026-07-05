"""JSON SSE helpers for agent streaming routes."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from pika.core.agno_context import build_user_dependencies
from pika.core.context import get_user_id


def namespaced_session_id(client_session_id: str | None) -> str | None:
    """Bind client session to authenticated user when context is set."""
    if not client_session_id:
        return None
    user_id = get_user_id()
    if user_id:
        return f"{user_id}:{client_session_id}"
    return client_session_id


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_agent_json(
    agent,
    message: str,
    *,
    session_id: str | None = None,
    extra_dependencies: dict | None = None,
    stream_events: bool = True,
) -> AsyncIterator[str]:
    """Yield JSON SSE frames from agent.arun(stream=True)."""
    kwargs: dict[str, Any] = {}
    if session_id:
        kwargs["session_id"] = session_id

    deps = build_user_dependencies(extra_dependencies)
    if deps:
        kwargs["dependencies"] = deps
        kwargs["add_dependencies_to_context"] = True

    if not hasattr(agent, "arun"):
        yield sse_event({"type": "error", "message": "agent does not support streaming"})
        return

    async for chunk in agent.arun(message, stream=True, stream_events=stream_events, **kwargs):
        event = getattr(chunk, "event", None)
        if event == "ToolCallStarted":
            tool = getattr(chunk, "tool", None)
            yield sse_event(
                {
                    "type": "tool",
                    "name": getattr(tool, "tool_name", None),
                    "status": "started",
                }
            )
            continue
        if event == "ToolCallCompleted":
            tool = getattr(chunk, "tool", None)
            yield sse_event(
                {
                    "type": "tool",
                    "name": getattr(tool, "tool_name", None),
                    "status": "completed",
                }
            )
            continue

        content = getattr(chunk, "content", None)
        if content:
            yield sse_event({"type": "delta", "text": str(content)})

    yield sse_event({"type": "done"})
