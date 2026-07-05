"""Agno context-engineering helpers (https://docs.agno.com/context/agent/overview).

Builds system/user message context from agent class attrs, YAML config, and
per-run dependency injection.
"""
from __future__ import annotations

import pathlib
from typing import Any

import yaml

from pika.core.context import get_role, get_tenant_id, get_user_id

# Agno Agent kwargs that pika forwards from class attributes when not set in
# config or call-time kwargs. Keep in sync with Agno's Agent.__init__.
AGNO_CONTEXT_ATTRS: tuple[str, ...] = (
    "role",
    "expected_output",
    "additional_context",
    "additional_input",
    "markdown",
    "use_instruction_tags",
    "add_datetime_to_context",
    "add_name_to_context",
    "add_location_to_context",
    "add_history_to_context",
    "num_history_runs",
    "num_history_messages",
    "max_tool_calls_from_history",
    "add_knowledge_to_context",
    "add_dependencies_to_context",
    "add_memories_to_context",
    "add_session_summary_to_context",
    "add_session_state_to_context",
    "enable_agentic_knowledge_filters",
    "search_knowledge",
    "timezone_identifier",
    "datetime_format",
    "system_message",
    "build_context",
)


def resolve_attr(agent: Any, name: str, agent_kwargs: dict, call_kwargs: dict) -> Any:
    """Precedence: call-time kwargs > agent YAML > class attribute."""
    if name in call_kwargs and call_kwargs[name] is not None:
        return call_kwargs.pop(name)
    if name in agent_kwargs and agent_kwargs[name] is not None:
        return agent_kwargs.pop(name)
    return getattr(agent, name, None)


def collect_context_kwargs(agent: Any, agent_kwargs: dict, call_kwargs: dict) -> dict[str, Any]:
    """Pull Agno context params from class attrs into kwargs for Agent.__init__."""
    out: dict[str, Any] = {}
    for name in AGNO_CONTEXT_ATTRS:
        value = resolve_attr(agent, name, agent_kwargs, call_kwargs)
        if value is not None:
            out[name] = value
    return out


def load_training_examples(agent_id: str) -> list | None:
    """Load few-shot examples from agents/<id>/training_examples.yaml."""
    root = pathlib.Path.cwd()
    path = root / "agents" / agent_id / "training_examples.yaml"
    if not path.exists():
        return None

    raw = yaml.safe_load(path.read_text()) or []
    if isinstance(raw, dict):
        raw = raw.get("examples") or raw.get("training_examples") or []
    if not isinstance(raw, list) or not raw:
        return None

    from agno.models.message import Message

    messages: list[Message] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        user_text = item.get("input") or item.get("user")
        assistant_text = item.get("output") or item.get("assistant")
        if user_text:
            messages.append(Message(role="user", content=str(user_text).strip()))
        if assistant_text:
            messages.append(Message(role="assistant", content=str(assistant_text).strip()))
    return messages or None


def build_user_dependencies(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Per-turn identity and optional calendar context via Agno dependencies."""
    deps: dict[str, Any] = {}
    try:
        from pika.config.loader import get_settings
        from pika.context.datetime import build_relative_date_context

        tz = get_settings().get("context", {}).get("timezone")
        if get_settings().get("context", {}).get("relative_dates", True):
            deps.update(build_relative_date_context(tz_name=tz))
    except Exception:
        pass
    if user_id := get_user_id():
        deps["user_id"] = user_id
    if tenant_id := get_tenant_id():
        deps["tenant_id"] = tenant_id
    if role := get_role():
        deps["role"] = role
    if extra:
        deps.update(extra)
    return deps


def apply_knowledge_defaults(agent_kwargs: dict, *, has_knowledge: bool) -> None:
    """When knowledge is configured, enable search unless explicitly disabled."""
    if not has_knowledge:
        return
    agent_kwargs.setdefault("search_knowledge", True)
    agent_kwargs.setdefault("add_knowledge_to_context", True)
