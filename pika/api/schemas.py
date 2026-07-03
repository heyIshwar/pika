"""Pydantic v2 schemas for the pika REST API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    context: Dict[str, Any] = {}


class RunResponse(BaseModel):
    run_id: str
    agent_id: str
    output: str
    trace_id: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentInfo(BaseModel):
    id: str
    owner: str
    description: str
    path: str


class TraceInfo(BaseModel):
    trace_id: str
    name: str
    status: str
    agent_id: Optional[str] = None
    duration_ms: Optional[int] = None
    total_spans: Optional[int] = None
    created_at: Optional[str] = None


class SpanInfo(BaseModel):
    span_id: str
    trace_id: str
    name: str
    span_kind: str
    status_code: str
    duration_ms: int
    attributes: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    vectordb: str
    cache: str
