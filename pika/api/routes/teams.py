"""Team routes."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from pika.api.run_helpers import run_kwargs
from pika.api.schemas import RunRequest, RunResponse
from pika.core.context import get_trace_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("/{team_id}/run", response_model=RunResponse)
async def run_team(team_id: str, req: RunRequest):
    from pika.cli.commands.loader import load_agent

    try:
        team = load_agent(team_id)
    except (ModuleNotFoundError, ValueError, RuntimeError) as exc:
        logger.exception("Failed to load team %s", team_id)
        raise HTTPException(status_code=404, detail="Team not found") from exc

    run_id = str(uuid4())
    start = time.monotonic()
    try:
        result = await team.run(req.message, **run_kwargs(req))
    except Exception as exc:
        logger.exception("Team run failed: %s", team_id)
        raise HTTPException(status_code=500, detail="Team run failed") from exc
    output = result.content if hasattr(result, "content") else str(result)
    duration_ms = int((time.monotonic() - start) * 1000)

    return RunResponse(
        run_id=run_id,
        agent_id=team_id,
        output=output,
        trace_id=get_trace_id(),
        duration_ms=duration_ms,
    )
