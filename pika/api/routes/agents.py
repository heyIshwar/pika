"""Agent routes: list, run, stream."""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pika.api.schemas import AgentInfo, RunRequest, RunResponse
from pika.core.context import get_trace_id

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
    except (ModuleNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    run_id = str(uuid4())
    start = time.monotonic()

    kwargs = {}
    if req.session_id:
        kwargs["session_id"] = req.session_id
    if req.user_id:
        kwargs["user_id"] = req.user_id
    if req.context:
        kwargs["dependencies"] = req.context
        kwargs["add_dependencies_to_context"] = True

    result = await agent.run(req.message, **kwargs)
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
    except (ModuleNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not hasattr(agent, "stream"):
        raise HTTPException(status_code=400, detail="Agent does not support streaming")

    kwargs = {}
    if req.session_id:
        kwargs["session_id"] = req.session_id
    if req.user_id:
        kwargs["user_id"] = req.user_id

    async def event_stream():
        async for chunk in agent.stream(req.message, **kwargs):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
