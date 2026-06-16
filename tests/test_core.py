import pytest

from pika.cli_commands.registry import validate_registry
from pika.config.loader import get_config
from pika.infra.cache import CacheManager


def test_get_config_agent():
    cfg = get_config("agents", "getting_started")
    assert cfg["llm_provider"]["name"] == "openai"


def test_registry_valid():
    validate_registry()


@pytest.mark.asyncio
async def test_cache_roundtrip():
    cache = CacheManager()
    await cache.set("test_agent", "hello", {"content": "world"})
    val = await cache.get("test_agent", "hello")
    assert val == {"content": "world"}
