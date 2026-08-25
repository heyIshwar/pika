"""Ingest existing infra (docs/files/URLs) and existing databases into an agent's knowledge base.

This is the read/RAG counterpart to `pika connect` (which generates action
tools from an OpenAPI spec): instead of letting an agent call an existing
system, it lets an agent semantically search over it.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pika.config.loader import get_config
from pika.infra.db import get_engine, get_knowledge

logger = logging.getLogger(__name__)

_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.google.com",
        "169.254.169.254",
    }
)


def _knowledge_for(agent_id: str):
    cfg = get_config("agents", agent_id).get("knowledge") or {}
    collection = cfg.get("collection", f"{agent_id}_knowledge")
    return get_knowledge(
        collection,
        embedder_name=cfg.get("embedder"),
        max_results=cfg.get("max_results", 10),
    )


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_ingest_url(url: str) -> None:
    """Reject non-http(s) and URLs resolving to private/link-local/metadata hosts."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are allowed for ingest")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL missing host")
    if host in _BLOCKED_HOSTS or host.endswith(".internal"):
        raise ValueError(f"Blocked host for ingest: {host}")

    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {host}") from exc

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise ValueError(f"Blocked private/link-local address for ingest: {ip}")


def validate_ingest_path(path: str, sandbox: Path | None = None) -> Path:
    """Require local paths to resolve under project sandbox (cwd by default)."""
    root = (sandbox or Path.cwd()).resolve()
    target = Path(path).expanduser().resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Path '{path}' is outside the project sandbox ({root})"
        ) from exc
    if not target.exists():
        raise ValueError(f"Path does not exist: {target}")
    return target


async def ingest_path(agent_id: str, path: str) -> None:
    """Ingest a file, directory, or URL into an agent's knowledge base.

    Uses Agno's built-in readers (PDF, CSV, DOCX, Markdown, website, ...),
    auto-selected by file extension / URL.
    """
    knowledge = _knowledge_for(agent_id)
    if path.startswith("http://") or path.startswith("https://"):
        validate_ingest_url(path)
        await knowledge.ainsert(url=path, metadata={"source": "url", "agent_id": agent_id})
    else:
        safe = validate_ingest_path(path)
        await knowledge.ainsert(
            path=str(safe), metadata={"source": "path", "agent_id": agent_id}
        )


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
