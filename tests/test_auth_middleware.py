"""Auth middleware fail-closed behavior."""
from __future__ import annotations

import os

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("PIKA_API_KEY", raising=False)
    monkeypatch.setenv("PIKA_ENV", "development")
    from pika.api.app import create_app

    return create_app(include_agent_routes=False)


def test_prod_without_api_key_returns_503(monkeypatch, app):
    monkeypatch.setenv("PIKA_ENV", "production")
    monkeypatch.delenv("PIKA_API_KEY", raising=False)
    client = TestClient(app)
    r = client.get("/traces")
    assert r.status_code == 503
    assert "PIKA_API_KEY" in r.json()["detail"]


def test_health_open_in_prod_without_key(monkeypatch, app):
    monkeypatch.setenv("PIKA_ENV", "production")
    monkeypatch.delenv("PIKA_API_KEY", raising=False)
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200


def test_wrong_key_401(monkeypatch, app):
    monkeypatch.setenv("PIKA_ENV", "development")
    monkeypatch.setenv("PIKA_API_KEY", "secret-key")
    client = TestClient(app)
    r = client.get("/traces", headers={"X-Pika-Key": "wrong"})
    assert r.status_code == 401


def test_correct_key_passes(monkeypatch, app):
    monkeypatch.setenv("PIKA_ENV", "development")
    monkeypatch.setenv("PIKA_API_KEY", "secret-key")
    client = TestClient(app)
    # /traces may 500 without DB, but must not be 401/503
    r = client.get("/traces", headers={"X-Pika-Key": "secret-key"})
    assert r.status_code not in (401, 503)
