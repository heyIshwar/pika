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


@pytest.mark.asyncio
async def test_cache_roundtrip():
    cache = CacheManager()
    await cache.set("test_agent", "hello", {"content": "world"})
    val = await cache.get("test_agent", "hello")
    assert val == {"content": "world"}
