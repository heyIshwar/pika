"""SSRF / path sandbox guards for knowledge ingest."""
from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from pika.knowledge.ingest import validate_db_url, validate_ingest_path, validate_ingest_url


def test_reject_file_scheme():
    with pytest.raises(ValueError, match="http"):
        validate_ingest_url("file:///etc/passwd")


def test_reject_loopback_literal():
    with pytest.raises(ValueError):
        validate_ingest_url("http://127.0.0.1/secret")


def test_reject_metadata_host():
    with pytest.raises(ValueError):
        validate_ingest_url("http://metadata.google.internal/latest")


def test_path_outside_sandbox(tmp_path):
    outside = Path("/etc/passwd")
    if not outside.exists():
        pytest.skip("no /etc/passwd")
    with pytest.raises(ValueError, match="outside"):
        validate_ingest_path(str(outside), sandbox=tmp_path)


def test_path_inside_sandbox(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# hi")
    assert validate_ingest_path(str(f), sandbox=tmp_path) == f.resolve()


# ---------- db_url validation (schema ingest) ----------


def _resolve_to(ip: str):
    """Patch getaddrinfo so `host` resolves to a single address."""
    def fake_getaddrinfo(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    return fake_getaddrinfo


def test_db_url_sqlite_passes_through():
    assert validate_db_url("sqlite:///pika.db") == "sqlite:///pika.db"


def test_db_url_rejects_unknown_scheme():
    with pytest.raises(ValueError, match="Unsupported db_url scheme"):
        validate_db_url("ftp://example.com/db")


def test_db_url_rejects_metadata_host():
    with patch(
        "pika.knowledge.ingest.socket.getaddrinfo", _resolve_to("169.254.169.254")
    ):
        with pytest.raises(ValueError, match="Blocked"):
            validate_db_url("postgresql://metadata.google.internal:5432/app")


def test_db_url_rejects_internal_suffix():
    with pytest.raises(ValueError, match="Blocked host"):
        validate_db_url("postgresql://db.prod.internal:5432/app")


def test_db_url_rejects_link_local_ip():
    with patch(
        "pika.knowledge.ingest.socket.getaddrinfo", _resolve_to("169.254.10.20")
    ):
        with pytest.raises(ValueError, match="link-local"):
            validate_db_url("mysql://innocent.example.com/db")


def test_db_url_allows_private_and_loopback_hosts():
    """Internal company DBs are the intended target — RFC1918/localhost allowed."""
    with patch(
        "pika.knowledge.ingest.socket.getaddrinfo", _resolve_to("10.1.2.3")
    ):
        assert (
            validate_db_url("postgresql://db.corp:5432/app")
            == "postgresql://db.corp:5432/app"
        )
    with patch(
        "pika.knowledge.ingest.socket.getaddrinfo", _resolve_to("127.0.0.1")
    ):
        assert validate_db_url("postgresql://localhost:5432/app")


def test_db_url_non_sqlite_requires_host():
    with pytest.raises(ValueError, match="no host"):
        validate_db_url("postgresql:///app")
