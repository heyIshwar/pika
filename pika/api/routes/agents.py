"""Agent routes: list, run, stream."""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pika.api.schemas import AgentInfo, RunRequest, RunResponse
from pika.api.streaming import namespaced_session_id, stream_agent_json
from pika.core.agno_context import build_user_dependencies
from pika.core.context import get_trace_id, get_user_id

router = APIRouter(prefix="/agents", tags=["agents"])


def _run_kwargs(req: RunRequest) -> dict:
    kwargs: dict = {}
    if req.session_id:
        kwargs["session_id"] = namespaced_session_id(req.session_id)
    # Prefer authenticated context over client-supplied body user_id
    ctx_user = get_user_id()
    if ctx_user:
        kwargs["user_id"] = ctx_user
    elif req.user_id:
        kwargs["user_id"] = req.user_id
    deps = build_user_dependencies(req.context or None)
    if deps:
        kwargs["dependencies"] = deps
        kwargs["add_dependencies_to_context"] = True
    return kwargs


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

    result = await agent.run(req.message, **_run_kwargs(req))
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

    kwargs = _run_kwargs(req)

    async def event_stream():
        async for frame in stream_agent_json(
            agent,
            req.message,
            session_id=kwargs.get("session_id"),
            extra_dependencies=kwargs.get("dependencies"),
        ):
            yield frame

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
