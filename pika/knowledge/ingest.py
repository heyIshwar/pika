"""Ingest existing infra (docs/files/URLs) and existing databases into an agent's knowledge base.

This is the read/RAG counterpart to `pika connect` (which generates action
tools from an OpenAPI spec): instead of letting an agent call an existing
system, it lets an agent semantically search over it.
"""
from __future__ import annotations

from typing import Optional

from pika.config.loader import get_config
from pika.infra.db import get_engine, get_knowledge


def _knowledge_for(agent_id: str):
    cfg = get_config("agents", agent_id).get("knowledge") or {}
    collection = cfg.get("collection", f"{agent_id}_knowledge")
    return get_knowledge(
        collection,
        embedder_name=cfg.get("embedder"),
        max_results=cfg.get("max_results", 10),
    )


async def ingest_path(agent_id: str, path: str) -> None:
    """Ingest a file, directory, or URL into an agent's knowledge base.

    Uses Agno's built-in readers (PDF, CSV, DOCX, Markdown, website, ...),
    auto-selected by file extension / URL.
    """
    knowledge = _knowledge_for(agent_id)
    if path.startswith("http://") or path.startswith("https://"):
        await knowledge.ainsert(url=path, metadata={"source": "url", "agent_id": agent_id})
    else:
        await knowledge.ainsert(path=path, metadata={"source": "path", "agent_id": agent_id})


async def ingest_database_schema(agent_id: str, db_url: Optional[str] = None) -> int:
    """Introspect an existing SQL database's schema and ingest it as searchable knowledge.

    Complements skills.database.DatabaseSkill (live querying): this lets an
    agent semantically find "which table/column has X" before it writes SQL.
    Returns the number of tables ingested.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.inspection import inspect

    engine = create_engine(db_url) if db_url else get_engine()
    inspector = inspect(engine)
    knowledge = _knowledge_for(agent_id)

    table_names = inspector.get_table_names()
    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        column_lines = "\n".join(
            f"  - {c['name']}: {c['type']}" + ("" if c["nullable"] else " (not null)") for c in columns
        )
        fks = inspector.get_foreign_keys(table_name)
        fk_lines = (
            "\n".join(
                f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}"
                for fk in fks
            )
            or "  (none)"
        )

        text_content = f"Table: {table_name}\nColumns:\n{column_lines}\nForeign keys:\n{fk_lines}"
        await knowledge.ainsert(
            name=f"schema:{table_name}",
            text_content=text_content,
            metadata={"source": "db_schema", "table": table_name, "agent_id": agent_id},
        )

    return len(table_names)
