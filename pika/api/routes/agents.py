"""Agent routes: list, run, stream."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pika.api.run_helpers import run_kwargs
from pika.api.schemas import AgentInfo, RunRequest, RunResponse
from pika.api.streaming import sse_event, stream_agent_json
from pika.core.context import get_trace_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
async def list_agents():
    from pika.cli.commands.loader import load_registry

    registry = load_registry()
    return [
        AgentInfo(
            id=a["id"],
            owner=a.get("owner", ""),
            description=a.get("description", ""),
            path=a.get("path", ""),
        )
        for a in registry.get("agents", [])
    ]


@router.post("/{agent_id}/run", response_model=RunResponse)
async def run_agent(agent_id: str, req: RunRequest):
    from pika.cli.commands.loader import load_agent

    try:
        agent = load_agent(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    except (ModuleNotFoundError, RuntimeError) as exc:
        logger.exception("Failed to load agent %s", agent_id)
        raise HTTPException(status_code=404, detail="Agent not found") from exc

    run_id = str(uuid4())
    start = time.monotonic()

    try:
        result = await agent.run(req.message, **run_kwargs(req))
    except Exception as exc:
        logger.exception("Agent run failed: %s", agent_id)
        raise HTTPException(status_code=500, detail="Agent run failed") from exc

    output = result.content if hasattr(result, "content") else str(result)
    duration_ms = int((time.monotonic() - start) * 1000)

    return RunResponse(
        run_id=run_id,
        agent_id=agent_id,
        output=output,
        trace_id=get_trace_id(),
        duration_ms=duration_ms,
    )


@router.post("/{agent_id}/stream")
async def stream_agent(agent_id: str, req: RunRequest):
    from pika.cli.commands.loader import load_agent

    try:
        agent = load_agent(agent_id)
    except (ModuleNotFoundError, ValueError, RuntimeError) as exc:
        logger.exception("Failed to load agent %s", agent_id)
        raise HTTPException(status_code=404, detail="Agent not found") from exc

    kwargs = run_kwargs(req)

    async def event_stream():
        try:
            async for frame in stream_agent_json(
                agent,
                req.message,
                session_id=kwargs.get("session_id"),
                extra_dependencies=kwargs.get("dependencies"),
            ):
                yield frame
        except Exception:
            # Headers/status are already sent for an SSE response, so a mid-stream
            # failure can't become an HTTPException — log server-side and emit a
            # generic error frame instead of leaking the exception to the client.
            logger.exception("Agent stream failed: %s", agent_id)
            yield sse_event({"type": "error", "message": "Stream failed. Check server logs for details."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
