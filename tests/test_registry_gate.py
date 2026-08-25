"""Registry gate on load_agent."""
from __future__ import annotations

import pytest

from pika.cli.commands.loader import assert_runnable, load_agent


def test_assert_runnable_rejects_unknown():
    with pytest.raises(ValueError, match="not registered"):
        assert_runnable("definitely_not_a_real_agent_xyz")


def test_load_agent_rejects_unregistered():
    with pytest.raises(ValueError, match="not registered"):
        load_agent("definitely_not_a_real_agent_xyz")
