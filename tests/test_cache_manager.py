"""CacheManager behavior: L1 TTL/bounds, versioned invalidation, write-through."""
from __future__ import annotations

import asyncio

from pika.infra.cache import CacheManager, CachedResponse


def _run(coro):
    return asyncio.run(coro)


class FakeRedis:
    """Records ops; backs get/set/incr with an in-memory dict."""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.set_calls: list[tuple[str, int | None]] = []

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value
        self.set_calls.append((key, ex))

    async def incr(self, key):
        current = int(self.data.get(key, "0")) + 1
        self.data[key] = str(current)
        return current


def test_l1_roundtrip_and_expiry():
    cache = CacheManager(ttl=0)
    _run(cache.set("agent", "hello", "world"))
    # ttl=0 → already expired on the next read.
    assert _run(cache.get("agent", "hello")) is None


def test_l1_max_entries_evicts_oldest():
    cache = CacheManager(max_entries=2)
    _run(cache.set("agent", "m1", CachedResponse(content="one")))
    _run(cache.set("agent", "m2", CachedResponse(content="two")))
    _run(cache.set("agent", "m3", CachedResponse(content="three")))

    assert len(cache._mem) == 2
    assert _run(cache.get("agent", "m1")) is None  # evicted (oldest)
    assert _run(cache.get("agent", "m3")).content == "three"


def test_invalidate_clears_local_entries_only_for_agent():
    cache = CacheManager()
    _run(cache.set("agent_a", "q", CachedResponse(content="a")))
    _run(cache.set("agent_b", "q", CachedResponse(content="b")))
    cache._redis = None  # force pure-local path even if REDIS_URL is set in env

    _run(cache.invalidate("agent_a"))

    assert _run(cache.get("agent_a", "q")) is None
    assert _run(cache.get("agent_b", "q")).content == "b"


def test_redis_invalidation_bumps_version():
    cache = CacheManager()
    fake = FakeRedis()
    cache._redis = fake

    _run(cache.set("agent", "q", {"answer": 42}))
    base_key = next(k for k in fake.data if k.startswith("pika") is False)
    assert base_key.endswith("@0"), "first write lands in generation 0"

    _run(cache.invalidate("agent"))
    assert fake.data["pika:cachver:agent"] == "1"

    # After the bump, a fresh set/read targets the new generation; the old L2
    # entry under @0 is unreachable.
    _run(cache.set("agent", "q", {"answer": 43}))
    assert f"{base_key.rsplit('@', 1)[0]}@1" in fake.data


def test_redis_get_rehydrates_cached_response():
    cache = CacheManager()
    fake = FakeRedis()
    cache._redis = fake

    _run(cache.set("agent", "q", CachedResponse(content="stored answer")))
    restored = _run(cache.get("agent", "q"))
    assert isinstance(restored, CachedResponse)
    assert restored.content == "stored answer"
    # L2 payload was written with a TTL, not permanently.
    assert fake.set_calls[0][1] == cache._ttl


def test_cached_response_has_content_attr():
    response = CachedResponse(content="hi")
    assert hasattr(response, "content")
