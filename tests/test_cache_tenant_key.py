"""Cache keys must include tenant/user to avoid cross-tenant leakage."""
from __future__ import annotations

from pika.core.context import set_tenant_id, set_user_id
from pika.infra.cache import CacheManager


def test_cache_key_differs_by_tenant():
    cache = CacheManager()
    set_tenant_id("tenant-a")
    set_user_id("user-1")
    key_a = cache._base_key("agent", "hello")

    set_tenant_id("tenant-b")
    set_user_id("user-1")
    key_b = cache._base_key("agent", "hello")

    set_tenant_id(None)
    set_user_id(None)

    assert key_a != key_b


def test_cache_key_differs_by_user():
    cache = CacheManager()
    set_tenant_id("t1")
    set_user_id("u1")
    key_a = cache._base_key("agent", "hello")

    set_user_id("u2")
    key_b = cache._base_key("agent", "hello")

    set_tenant_id(None)
    set_user_id(None)

    assert key_a != key_b
