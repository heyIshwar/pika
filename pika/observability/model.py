"""Pika span model — compatible with Agno's span table schema."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class SpanKind(str, Enum):
    AGENT_STEP = "AGENT_STEP"
    LLM_CALL = "LLM_CALL"
    TOOL_CALL = "TOOL_CALL"
    CORRECTION = "CORRECTION"
    MEMORY_RECALL = "MEMORY_RECALL"
    TEAM_RUN = "TEAM_RUN"
    PLAN_STEP = "PLAN_STEP"


@dataclass
class PikaSpan:
    """
    Lightweight span that can be written to Agno's spans table.

    Fields match Agno's tracing.schemas.Span so create_span() accepts it.
    """

    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    span_kind: str
    status_code: str
    status_message: Optional[str]
    start_time: datetime
    end_time: datetime
    duration_ms: int
    attributes: Dict[str, Any]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        data["end_time"] = self.end_time.isoformat()
        data["created_at"] = self.created_at.isoformat()
        return data
