import pytest

from pika.knowledge.okf import ingest_okf_bundle, parse_okf_file


class FakeKnowledge:
    def __init__(self):
        self.inserted: list[dict] = []

    async def ainsert(self, *, name, text_content, metadata):
        self.inserted.append({"name": name, "text_content": text_content, "metadata": metadata})


def test_parse_okf_file_valid(tmp_path):
    path = tmp_path / "orders.md"
    path.write_text(
        "---\n"
        "type: MongoDB Collection\n"
        "title: orders\n"
        "description: Customer orders.\n"
        "tags: [order, orders]\n"
        "---\n"
        "# orders\n\nSchema details.\n"
    )
    parsed = parse_okf_file(path)
    assert parsed is not None
    assert parsed["meta"]["title"] == "orders"
    assert "Schema details" in parsed["body"]


@pytest.mark.asyncio
async def test_ingest_okf_bundle_skips_reserved(tmp_path):
    tables = tmp_path / "tables"
    tables.mkdir()
    (tables / "index.md").write_text("---\ntype: index\ntitle: nav\n---\nignored")
    (tables / "orders.md").write_text(
        "---\ntype: MongoDB Collection\ntitle: orders\ntags: [order]\n---\n# orders\n"
    )
    kb = FakeKnowledge()
    report = await ingest_okf_bundle(kb, [tables])
    assert report.ok_count == 1
    assert len(report.skipped) == 1
    assert not report.failed
    assert kb.inserted[0]["metadata"]["kind"] == "okf"


@pytest.mark.asyncio
async def test_ingest_okf_bundle_isolates_failures(tmp_path):
    """One failing insert must not abort the remaining files."""
    tables = tmp_path / "tables"
    tables.mkdir()
    (tables / "a_orders.md").write_text(
        "---\ntype: Collection\ntitle: orders\n---\nbody"
    )
    (tables / "b_users.md").write_text(
        "---\ntype: Collection\ntitle: users\n---\nbody"
    )

    class PartlyBrokenKnowledge(FakeKnowledge):
        async def ainsert(self, *, name, text_content, metadata):
            if "users" in name:
                raise RuntimeError("lance write failed")
            await super().ainsert(name=name, text_content=text_content, metadata=metadata)

    kb = PartlyBrokenKnowledge()
    report = await ingest_okf_bundle(kb, [tables])
    assert report.ok == ["orders"]
    assert len(report.failed) == 1
    assert "users" in report.failed[0]["target"]
    assert "lance write failed" in report.failed[0]["error"]
