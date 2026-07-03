"""Trace routes — reads from Agno's DB trace/span tables."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from pika.api.schemas import SpanInfo, TraceInfo

router = APIRouter(prefix="/traces", tags=["traces"])


def _db():
    from pika.infra.storage import get_storage

    return get_storage()


@router.get("", response_model=List[TraceInfo])
async def list_traces(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    db = _db()
    try:
        traces, _ = db.get_traces(agent_id=agent_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result = []
    for t in traces:
        if hasattr(t, "__dict__"):
            d = t.__dict__
        elif hasattr(t, "_asdict"):
            d = t._asdict()
        elif isinstance(t, dict):
            d = t
        else:
            d = {}

        result.append(
            TraceInfo(
                trace_id=d.get("trace_id", ""),
                name=d.get("name", ""),
                status=d.get("status", ""),
                agent_id=d.get("agent_id"),
                duration_ms=d.get("duration_ms"),
                total_spans=d.get("total_spans"),
                created_at=str(d.get("created_at", "")),
            )
        )
    return result


@router.get("/{trace_id}", response_model=List[SpanInfo])
async def get_trace_spans(trace_id: str):
    db = _db()
    try:
        spans = db.get_spans(trace_id=trace_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result = []
    for span in spans:
        if hasattr(span, "__dict__"):
            d = span.__dict__
        elif isinstance(span, dict):
            d = span
        else:
            d = {}

        result.append(
            SpanInfo(
                span_id=d.get("span_id", ""),
                trace_id=d.get("trace_id", trace_id),
                name=d.get("name", ""),
                span_kind=d.get("span_kind", ""),
                status_code=d.get("status_code", ""),
                duration_ms=d.get("duration_ms", 0),
                attributes=d.get("attributes") or {},
            )
        )
    return result
