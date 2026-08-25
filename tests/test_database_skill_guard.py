"""DatabaseSkill / DatabaseTool security guards."""
from __future__ import annotations

import pytest

from skills.database.tool import _assert_read_only_sql


def test_read_only_allows_select():
    _assert_read_only_sql("SELECT 1")
    _assert_read_only_sql("  with x as (select 1) select * from x")


def test_read_only_blocks_writes():
    with pytest.raises(ValueError):
        _assert_read_only_sql("DELETE FROM users")
    with pytest.raises(ValueError):
        _assert_read_only_sql("INSERT INTO t VALUES (1)")
    with pytest.raises(ValueError):
        _assert_read_only_sql("DROP TABLE users")
    with pytest.raises(ValueError):
        _assert_read_only_sql("SELECT 1; DROP TABLE users")


def test_control_plane_db_blocked_by_default(monkeypatch):
    monkeypatch.setattr("pika.core.tool.get_config", lambda *a, **k: {})
    from skills.database.tool import DatabaseTool

    with pytest.raises(RuntimeError, match="db_url"):
        DatabaseTool()
