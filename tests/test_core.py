import pytest

from pika.cli.commands.registry import validate_registry
from pika.config.loader import get_config
from pika.infra.cache import CacheManager


def test_get_config_agent():
    cfg = get_config("agents", "getting_started")
    # llm_provider is optional per-agent; falls back to config/llm_providers/default.yaml
    assert isinstance(cfg, dict)


def test_registry_valid():
    validate_registry()


def test_base_agent_forwards_class_description(monkeypatch):
    """Agno Agent.__init__ must not wipe subclass description/instructions."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from agents.getting_started.agent import GettingStartedAgent

    agent = GettingStartedAgent()
    assert agent.description
    assert agent.instructions


@pytest.mark.asyncio
async def test_cache_roundtrip():
    cache = CacheManager()
    await cache.set("test_agent", "hello", {"content": "world"})
    val = await cache.get("test_agent", "hello")
    assert val == {"content": "world"}
