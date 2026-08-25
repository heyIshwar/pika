"""Shared run kwargs for agent/team API routes."""
from __future__ import annotations

from pika.api.schemas import RunRequest
from pika.api.streaming import namespaced_session_id
from pika.core.agno_context import build_user_dependencies
from pika.core.context import get_user_id


def run_kwargs(req: RunRequest) -> dict:
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
