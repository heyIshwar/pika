import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")

_DEFAULT_TTL = 3600
_DEFAULT_MAX_ENTRIES = 1024

_VERSION_KEY_PREFIX = "pika:cachver:"
_NO_VERSION = "0"


class CachedResponse:
    """Minimal response shape restored from cache layers (exposes .content)."""

    __slots__ = ("content",)

    def __init__(self, content: Any):
        self.content = content

    def __repr__(self) -> str:
        text = self.content if isinstance(self.content, str) else str(self.content)
        return f"CachedResponse({text[:80]!r})"


class CacheManager:
    """Two-tier cache: bounded in-memory L1 + optional Redis L2.

    - L1 entries expire after ``ttl`` seconds and the map is capped at
      ``max_entries`` (LRU eviction) instead of growing unbounded.
    - Every key carries a per-agent version. :meth:`invalidate` bumps the
      version in Redis, so *all* processes/replicas stop serving that agent's
      stale entries — previously L2 (and other replicas' L1) kept old answers.
    """

    def __init__(
        self,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        ttl: int = _DEFAULT_TTL,
    ):
        self._mem: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_entries = max(1, max_entries)
        self._ttl = ttl
        self._keys_by_agent: dict[str, set[str]] = {}
        self._redis = None
        if REDIS_URL:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    def _base_key(self, agent_id: str, message: str) -> str:
        try:
            from pika.core.context import get_tenant_id, get_user_id

            tenant = get_tenant_id() or ""
            user = get_user_id() or ""
        except Exception:
            tenant = ""
            user = ""
        raw = f"{agent_id}::{tenant}::{user}::{message}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def _version(self, agent_id: str) -> str:
        """Current cache generation for an agent ('bumped' on invalidate)."""
        if self._redis is None:
            return _NO_VERSION
        return await self._redis.get(f"{_VERSION_KEY_PREFIX}{agent_id}") or _NO_VERSION

    def _get_fresh_l1(self, key: str) -> Optional[Any]:
        entry = self._mem.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= time.monotonic():
            del self._mem[key]
            return None
        self._mem.move_to_end(key)
        return value

    async def get(self, agent_id: str, message: str) -> Optional[Any]:
        base = self._base_key(agent_id, message)
        version = await self._version(agent_id)
        key = f"{version}:{base}"

        fresh = self._get_fresh_l1(key)
        if fresh is not None:
            return fresh

        if self._redis:
            val = await self._redis.get(f"{base}@{version}")
            if val:
                try:
                    data = json.loads(val)
                except (TypeError, ValueError):
                    logger.warning("cache: undecodable L2 payload dropped")
                    return None
                if isinstance(data, dict) and "content" in data:
                    return CachedResponse(content=data["content"])
                return data
        return None

    async def set(self, agent_id: str, message: str, value: Any, ttl: Optional[int] = None):
        effective_ttl = self._ttl if ttl is None else ttl
        base = self._base_key(agent_id, message)
        version = await self._version(agent_id)

        # L1 (LRU-bounded, expiring)
        l1_key = f"{version}:{base}"
        self._mem[l1_key] = (value, time.monotonic() + effective_ttl)
        self._mem.move_to_end(l1_key)
        self._keys_by_agent.setdefault(agent_id, set()).add(l1_key)
        while len(self._mem) > self._max_entries:
            evicted_key, _ = self._mem.popitem(last=False)
            for keys in self._keys_by_agent.values():
                keys.discard(evicted_key)

        # L2
        if self._redis:
            payload = value
            if hasattr(value, "content"):
                payload = {"content": value.content}
            elif not isinstance(value, (dict, list)):
                payload = {"content": str(value)}
            await self._redis.set(
                f"{base}@{version}", json.dumps(payload, default=str), ex=effective_ttl
            )

    async def invalidate(self, agent_id: str):
        """Drop this agent's cached responses everywhere.

        Local L1 entries are deleted directly; with Redis configured, the
        agent's version counter is bumped so every replica immediately stops
        hitting the old generation of keys (L2 included).
        """
        for key in self._keys_by_agent.pop(agent_id, set()):
            self._mem.pop(key, None)
        if self._redis:
            try:
                await self._redis.incr(f"{_VERSION_KEY_PREFIX}{agent_id}")
            except Exception:
                logger.warning(
                    "cache: failed to bump version for %s; L2 may serve stale "
                    "entries until TTL expiry",
                    agent_id,
                    exc_info=True,
                )
