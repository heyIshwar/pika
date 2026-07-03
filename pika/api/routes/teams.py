"""Team routes."""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from pika.api.schemas import RunRequest, RunResponse
from pika.core.context import get_trace_id

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("/{team_id}/run", response_model=RunResponse)
async def run_team(team_id: str, req: RunRequest):
    from pika.cli.commands.loader import load_agent

    try:
        team = load_agent(team_id)
    except (ModuleNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    run_id = str(uuid4())
    start = time.monotonic()
    result = await team.run(req.message)
    output = result.content if hasattr(result, "content") else str(result)
    duration_ms = int((time.monotonic() - start) * 1000)

    return RunResponse(
        run_id=run_id,
        agent_id=team_id,
        output=output,
        trace_id=get_trace_id(),
        duration_ms=duration_ms,
    )
