"""In-process message bus using asyncio queues."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator


class InMemoryBus:
    """Simple pub/sub bus using per-topic asyncio.Queue instances."""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, topic: str, message: Any) -> None:
        for q in self._queues.get(topic, []):
            await q.put(message)

    async def subscribe(self, topic: str) -> AsyncIterator[Any]:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[topic].append(q)
        try:
            while True:
                msg = await q.get()
                if msg is _STOP_SENTINEL:
                    break
                yield msg
        finally:
            self._queues[topic].remove(q)

    async def close_topic(self, topic: str) -> None:
        for q in self._queues.get(topic, []):
            await q.put(_STOP_SENTINEL)


_STOP_SENTINEL = object()
