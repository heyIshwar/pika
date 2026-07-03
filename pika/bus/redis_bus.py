"""Redis-backed pub/sub bus for distributed deployments."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator


class RedisBus:
    """Message bus backed by Redis pub/sub (requires redis[asyncio] extra)."""

    def __init__(self, redis_url: str):
        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError("Install redis extra: pip install 'pika-agents[redis]'")
        self._redis_url = redis_url
        self._client = aioredis.from_url(redis_url)

    async def publish(self, topic: str, message: Any) -> None:
        payload = json.dumps(message) if not isinstance(message, str) else message
        await self._client.publish(topic, payload)

    async def subscribe(self, topic: str) -> AsyncIterator[Any]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(topic)
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                data = msg["data"]
                try:
                    yield json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    yield data
