"""Factory: return InMemoryBus or RedisBus based on REDIS_URL."""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_bus():
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        from pika.bus.redis_bus import RedisBus

        return RedisBus(redis_url)
    from pika.bus.memory_bus import InMemoryBus

    return InMemoryBus()
