"""Per-file error isolation for knowledge ingest runs."""
from __future__ import annotations

import asyncio
import json

import pytest

from pika.knowledge.ingest import IngestReport, ingest_path


class FakeKnowledge:
    """Records inserts; optionally fails on paths containing 'poison'."""

    def __init__(self, fail_on: str | None = "poison"):
        self.inserted: list[str] = []
        self.fail_on = fail_on

    async def ainsert(self, *, url=None, path=None, metadata=None):
        target = url or path or ""
        if self.fail_on and self.fail_on in target:
            raise RuntimeError(f"simulated insert failure for {target}")
        self.inserted.append(target)


@pytest.fixture()
def fake_kb(monkeypatch):
    kb = FakeKnowledge()
    monkeypatch.setattr("pika.knowledge.ingest._knowledge_for", lambda agent_id: kb)
    return kb


def _run(coro):
    return asyncio.run(coro)


def test_directory_ingest_isolates_bad_file(tmp_path, monkeypatch, fake_kb):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "good_a.md").write_text("# a")
    (tmp_path / "poison.md").write_text("# boom")
    (tmp_path / "good_b.md").write_text("# b")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "good_c.md").write_text("# c")

    report = _run(ingest_path("agent_x", str(tmp_path)))

    assert sorted(report.ok) == [
        str(tmp_path / "good_a.md"),
        str(tmp_path / "good_b.md"),
        str(sub / "good_c.md"),
    ]
    assert len(report.failed) == 1
    assert "poison" in report.failed[0]["target"]
    assert "simulated insert failure" in report.failed[0]["error"]
    # The good files were still ingested despite the poison file.
    assert len(fake_kb.inserted) == 3


def test_directory_ingest_skips_hidden_and_junk(tmp_path, monkeypatch, fake_kb):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".hidden.md").write_text("# h")
    (tmp_path / "visible.md").write_text("# v")
    junk = tmp_path / "__pycache__"
    junk.mkdir()
    (junk / "junk.md").write_text("# j")

    report = _run(ingest_path("agent_x", str(tmp_path)))

    assert report.ok == [str(tmp_path / "visible.md")]
    assert not report.failed


def test_url_failure_is_recorded_not_raised(monkeypatch, fake_kb):
    # Loopback URLs are rejected by the SSRF guard — must land in report.failed.
    report = _run(ingest_path("agent_x", "http://127.0.0.1/secret"))
    assert not report.ok
    assert len(report.failed) == 1
    assert "127.0.0.1" in report.failed[0]["error"] or "Blocked" in report.failed[0][
        "error"
    ]


def test_report_defaults():
    report = IngestReport()
    assert report.ok_count == 0
    assert report.ok == []
    assert json.dumps({"ok": report.ok_count})  # trivially serializable for callers
