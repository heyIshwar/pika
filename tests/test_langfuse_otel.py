"""Langfuse OTEL setup tests."""
import os

from pika.observability import langfuse_otel


def test_install_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    langfuse_otel._installed = False
    langfuse_otel._otel_active = False
    assert langfuse_otel.install_langfuse_otel() is False
    assert langfuse_otel.langfuse_otel_active() is False


def test_install_skips_when_keys_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    langfuse_otel._installed = False
    langfuse_otel._otel_active = False
    assert langfuse_otel.install_langfuse_otel() is False


def test_install_idempotent(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    langfuse_otel._installed = True
    langfuse_otel._otel_active = True
    assert langfuse_otel.install_langfuse_otel() is True
