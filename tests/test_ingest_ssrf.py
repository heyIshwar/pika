"""SSRF / path sandbox guards for knowledge ingest."""
from __future__ import annotations

from pathlib import Path

import pytest

from pika.knowledge.ingest import validate_ingest_path, validate_ingest_url


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
