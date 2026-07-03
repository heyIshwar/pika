import pytest
from sqlalchemy import create_engine, text

from pika.infra.db import get_embedder, get_knowledge
from pika.knowledge.ingest import ingest_database_schema
from skills.database.skill import DatabaseSkill


def _patch_vectordb_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "pika.config.loader.get_settings",
        lambda: {"vectordb": {"provider": "lancedb", "path": str(tmp_path / ".lance")}},
    )
    # Isolate contents_db too, so ingestion doesn't write into the real project pika.db.
    from agno.db.sqlite import SqliteDb

    monkeypatch.setattr(
        "pika.infra.storage.get_storage", lambda: SqliteDb(db_url=f"sqlite:///{tmp_path}/test.db")
    )


def test_get_embedder_openai():
    from agno.knowledge.embedder.openai import OpenAIEmbedder

    assert isinstance(get_embedder("openai"), OpenAIEmbedder)


def test_get_embedder_unknown_raises():
    with pytest.raises(ValueError):
        get_embedder("not-a-real-embedder")


def test_get_knowledge_builds_real_knowledge(tmp_path, monkeypatch):
    _patch_vectordb_path(monkeypatch, tmp_path)

    from agno.knowledge.knowledge import Knowledge
    from agno.vectordb.lancedb import LanceDb

    knowledge = get_knowledge("test_collection", max_results=3)
    assert isinstance(knowledge, Knowledge)
    assert isinstance(knowledge.vector_db, LanceDb)
    assert knowledge.max_results == 3


@pytest.mark.asyncio
async def test_ingest_database_schema(tmp_path, monkeypatch):
    _patch_vectordb_path(monkeypatch, tmp_path)
    monkeypatch.setattr("pika.knowledge.ingest.get_config", lambda section, key: {})

    db_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT NOT NULL)"))

    count = await ingest_database_schema("schema_test_agent", db_url=f"sqlite:///{db_path}")
    assert count == 1


def test_database_skill_exposes_sql_tools(monkeypatch):
    monkeypatch.setattr(
        "pika.core.tool.get_config", lambda section, key: {"db_url": "sqlite:///:memory:"}
    )

    tools = DatabaseSkill().get_tools()
    names = {t.__name__ for t in tools}
    assert names == {"list_tables", "describe_table", "run_sql_query"}
