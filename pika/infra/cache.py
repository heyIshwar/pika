import hashlib
import json
import os
from typing import Any, Optional

REDIS_URL = os.getenv("REDIS_URL", "")


class CacheManager:
    """Two-tier cache: in-memory L1 + optional Redis L2."""

    def __init__(self):
        self._mem: dict[str, Any] = {}
        self._redis = None
        if REDIS_URL:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    def _key(self, agent_id: str, message: str) -> str:
        raw = f"{agent_id}::{message}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def get(self, agent_id: str, message: str) -> Optional[Any]:
        key = self._key(agent_id, message)
        if key in self._mem:
            return self._mem[key]
        if self._redis:
            val = await self._redis.get(key)
            if val:
                return json.loads(val)
        return None

    async def set(self, agent_id: str, message: str, value: Any, ttl: int = 3600):
        key = self._key(agent_id, message)
        self._mem[key] = value
        if self._redis:
            payload = value
            if hasattr(value, "content"):
                payload = {"content": value.content}
            await self._redis.set(key, json.dumps(payload, default=str), ex=ttl)

    async def invalidate(self, agent_id: str):
        prefix = hashlib.sha256(f"{agent_id}::".encode()).hexdigest()[:8]
        to_del = [k for k in self._mem if k.startswith(prefix)]
        for key in to_del:
            del self._mem[key]
