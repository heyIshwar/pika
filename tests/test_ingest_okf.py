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
    count = await ingest_okf_bundle(kb, [tables])
    assert count == 1
    assert kb.inserted[0]["metadata"]["kind"] == "okf"
