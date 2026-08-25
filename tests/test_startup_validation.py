"""Startup config validation: fail fast in production, warn elsewhere."""
from __future__ import annotations

import logging

import pytest

from pika.api.app import _validate_settings_at_startup


def test_production_raises_on_invalid_settings(monkeypatch):
    monkeypatch.setenv("PIKA_ENV", "production")
    monkeypatch.setattr(
        "pika.config.loader.get_settings",
        lambda: {"agno": {"num_history_runs": "not-an-int"}},
    )
    with pytest.raises(RuntimeError, match="Invalid pika configuration"):
        _validate_settings_at_startup()


def test_non_production_warns_but_continues(monkeypatch, caplog):
    monkeypatch.setenv("PIKA_ENV", "development")
    monkeypatch.setattr(
        "pika.config.loader.get_settings",
        lambda: {"agno": {"num_history_runs": "not-an-int"}},
    )
    with caplog.at_level(logging.WARNING):
        _validate_settings_at_startup()  # must not raise
    assert any("validation issue" in r.message for r in caplog.records)


def test_valid_settings_pass(monkeypatch):
    monkeypatch.setattr("pika.config.loader.get_settings", lambda: {})
    _validate_settings_at_startup()  # defaults validate cleanly
