"""Ingest existing infra (docs/files/URLs) and existing databases into an agent's knowledge base.

This is the read/RAG counterpart to `pika connect` (which generates action
tools from an OpenAPI spec): instead of letting an agent call an existing
system, it lets an agent semantically search over it.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
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

# URL schemes accepted for db-schema introspection (driver suffixes like
# postgresql+psycopg are allowed via the "+" split).
_DB_SCHEMES = frozenset(
    {"sqlite", "postgresql", "postgres", "mysql", "mariadb", "mssql", "oracle"}
)


@dataclass
class IngestReport:
    """Per-item outcome of an ingest run — one bad file must not abort the rest."""

    ok: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return len(self.ok)

    def record_failure(self, target: str, exc: Exception) -> None:
        logger.warning("ingest failed for %s: %s", target, exc)
        self.failed.append({"target": target, "error": str(exc)})


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


def _is_metadata_target(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Cloud metadata endpoints live in link-local space (e.g. 169.254.169.254).
    # Loopback/RFC1918 stay allowed for db targets: internal databases are the
    # intended ingest source and the operator already holds their credentials.
    return bool(ip.is_link_local)


def _resolve_and_check(
    host: str, port: int | None, *, what: str, strict_private: bool
) -> None:
    """Resolve a hostname and reject blocked targets.

    strict_private=True (web/URL ingest) also rejects RFC1918 private ranges —
    fetching arbitrary intranet URLs is a classic SSRF vector. For database
    targets strict_private=False: ingesting the schema of an internal company
    DB is the intended use, so only loopback/link-local/metadata hosts are
    blocked (the operator already holds that DB's credentials).
    """
    if host in _BLOCKED_HOSTS or host.endswith(".internal"):
        raise ValueError(f"Blocked host for {what}: {host}")

    try:
        infos = socket.getaddrinfo(host, port or 0, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve {what} host: {host}") from exc

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        blocked = _is_blocked_ip(ip) if strict_private else _is_metadata_target(ip)
        if blocked:
            raise ValueError(f"Blocked private/link-local address for {what}: {ip}")


def validate_ingest_url(url: str) -> None:
    """Reject non-http(s) URLs and URLs resolving to private/link-local/metadata hosts."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are allowed for ingest")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL missing host")
    _resolve_and_check(host, parsed.port, what="ingest", strict_private=True)


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


def validate_db_url(db_url: str) -> str:
    """Guard db-schema ingest targets against cloud-metadata / internal-host access.

    SQLite URLs pass through (no network host). Hosts resolving to loopback,
    link-local (incl. 169.254.169.254 cloud metadata), or *.internal names are
    rejected; RFC1918 private ranges are intentionally allowed because internal
    databases are the primary ingest target and the operator already holds
    their credentials.
    """
    parsed = urlparse(db_url)
    scheme = parsed.scheme.split("+")[0].lower()
    if scheme not in _DB_SCHEMES:
        raise ValueError(
            f"Unsupported db_url scheme '{parsed.scheme}'. "
            f"Expected one of: {sorted(_DB_SCHEMES)}"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        if scheme != "sqlite":
            raise ValueError(f"db_url has no host: {parsed.scheme}://...")
        return db_url
    _resolve_and_check(host, parsed.port, what="db ingest", strict_private=False)
    return db_url


def _iter_ingest_files(root: Path) -> list[Path]:
    """All real files under root, skipping hidden/junk entries."""
    skip_names = {"__pycache__", ".DS_Store", "node_modules"}
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part.startswith(".") or part in skip_names for part in rel_parts):
            continue
        files.append(p)
    return files


async def ingest_path(agent_id: str, path: str) -> IngestReport:
    """Ingest a file, directory, or URL into an agent's knowledge base.

    Uses Agno's built-in readers (PDF, CSV, DOCX, Markdown, website, ...),
    auto-selected by file extension / URL. Directories are ingested file by
    file so one bad document doesn't abort the whole run; the returned
    :class:`IngestReport` says what succeeded and what didn't.
    """
    knowledge = _knowledge_for(agent_id)
    report = IngestReport()

    if path.startswith("http://") or path.startswith("https://"):
        try:
            validate_ingest_url(path)
            await knowledge.ainsert(url=path, metadata={"source": "url", "agent_id": agent_id})
            report.ok.append(path)
        except Exception as exc:
            report.record_failure(path, exc)
        return report

    safe = validate_ingest_path(path)
    targets = _iter_ingest_files(safe) if safe.is_dir() else [safe]

    for target in targets:
        try:
            await knowledge.ainsert(
                path=str(target), metadata={"source": "path", "agent_id": agent_id}
            )
            report.ok.append(str(target))
        except Exception as exc:
            report.record_failure(str(target), exc)

    return report


async def ingest_database_schema(agent_id: str, db_url: Optional[str] = None) -> int:
    """Introspect an existing SQL database's schema and ingest it as searchable knowledge.

    Complements skills.database.DatabaseSkill (live querying): this lets an
    agent semantically find "which table/column has X" before it writes SQL.
    Per-table failures are logged and skipped instead of aborting the run.
    Returns the number of tables successfully ingested.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.inspection import inspect

    if db_url:
        validate_db_url(db_url)
    engine = create_engine(db_url) if db_url else get_engine()
    inspector = inspect(engine)
    knowledge = _knowledge_for(agent_id)

    ingested = 0
    for table_name in inspector.get_table_names():
        try:
            columns = inspector.get_columns(table_name)
            column_lines = "\n".join(
                f"  - {c['name']}: {c['type']}" + ("" if c["nullable"] else " (not null)")
                for c in columns
            )
            fks = inspector.get_foreign_keys(table_name)
            fk_lines = (
                "\n".join(
                    f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}"
                    for fk in fks
                )
                or "  (none)"
            )

            text_content = (
                f"Table: {table_name}\nColumns:\n{column_lines}\nForeign keys:\n{fk_lines}"
            )
            await knowledge.ainsert(
                name=f"schema:{table_name}",
                text_content=text_content,
                metadata={"source": "db_schema", "table": table_name, "agent_id": agent_id},
            )
            ingested += 1
        except Exception:
            logger.exception("schema ingest failed for table %s; skipping", table_name)

    return ingested
