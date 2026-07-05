"""Agno context-engineering helpers."""
from types import SimpleNamespace

from pika.core import agno_context
from pika.core.context import set_role, set_tenant_id, set_user_id


def test_load_training_examples_getting_started():
    messages = agno_context.load_training_examples("getting_started")
    assert messages is not None
    assert len(messages) >= 1
    assert messages[0].role == "user"


def test_build_user_dependencies_from_context():
    set_user_id("user-1")
    set_tenant_id("tenant-1")
    set_role("demo_user")
    try:
        deps = agno_context.build_user_dependencies()
        assert deps["user_id"] == "user-1"
        assert deps["tenant_id"] == "tenant-1"
        assert deps["role"] == "demo_user"
        assert "current_datetime" in deps
    finally:
        set_user_id(None)
        set_tenant_id(None)
        set_role(None)


def test_collect_context_kwargs_class_attrs():
    agent = SimpleNamespace(
        expected_output="format like this",
        markdown=True,
        add_datetime_to_context=True,
    )
    out = agno_context.collect_context_kwargs(agent, {}, {})
    assert out["expected_output"] == "format like this"
    assert out["markdown"] is True
    assert out["add_datetime_to_context"] is True


def test_collect_context_kwargs_precedence():
    agent = SimpleNamespace(markdown=False, num_history_runs=3)
    out = agno_context.collect_context_kwargs(
        agent,
        agent_kwargs={"markdown": True, "num_history_runs": 5},
        call_kwargs={"num_history_runs": 8},
    )
    assert out["markdown"] is True
    assert out["num_history_runs"] == 8


def test_apply_knowledge_defaults():
    kwargs: dict = {}
    agno_context.apply_knowledge_defaults(kwargs, has_knowledge=True)
    assert kwargs["search_knowledge"] is True
    assert kwargs["add_knowledge_to_context"] is True

    explicit = {"search_knowledge": False}
    agno_context.apply_knowledge_defaults(explicit, has_knowledge=True)
    assert explicit["search_knowledge"] is False


def test_load_training_examples_missing_agent():
    assert agno_context.load_training_examples("nonexistent_agent_xyz") is None
