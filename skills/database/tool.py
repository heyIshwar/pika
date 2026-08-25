from __future__ import annotations

import re

from pika.core.tool import BaseTool

_READ_ONLY_PREFIX = re.compile(
    r"^\s*(WITH\b|SELECT\b|SHOW\b|DESCRIBE\b|DESC\b|EXPLAIN\b)",
    re.IGNORECASE | re.DOTALL,
)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"ATTACH|DETACH|VACUUM|COPY|CALL|EXEC|EXECUTE|MERGE|INTO)\b",
    re.IGNORECASE,
)


def _assert_read_only_sql(sql: str) -> None:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Empty SQL rejected")
    # Reject multi-statement batches
    if ";" in cleaned:
        raise ValueError("Multi-statement SQL rejected")
    if not _READ_ONLY_PREFIX.match(cleaned):
        raise ValueError("Only read-only SQL is allowed (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN)")
    if _FORBIDDEN.search(cleaned):
        raise ValueError("Write/DDL SQL keywords are not allowed")


class DatabaseTool(BaseTool):
    """Exposes an existing SQL database (schema + queries) to agents via agno.tools.sql.SQLTools."""

    tool_id = "database"

    def __init__(self):
        super().__init__()
        from agno.tools.sql import SQLTools

        db_url = self._cfg.get("db_url")
        allow_control_plane = bool(self._cfg.get("allow_control_plane_db", False))
        enable_run_sql = bool(self._cfg.get("enable_run_sql_query", False))

        if db_url:
            self._sql = SQLTools(db_url=db_url, schema=self._cfg.get("schema"))
        elif allow_control_plane:
            from pika.infra.db import get_engine

            self._sql = SQLTools(db_engine=get_engine(), schema=self._cfg.get("schema"))
        else:
            raise RuntimeError(
                "DatabaseTool requires config/tools/database.yaml `db_url`, "
                "or `allow_control_plane_db: true` to use pika's own DATABASE_URL. "
                "Default is off to protect the control-plane DB."
            )

        self.list_tables = self._sql.list_tables
        self.describe_table = self._sql.describe_table
        self._enable_run_sql = enable_run_sql
        self._run_sql_raw = getattr(self._sql, "run_sql_query", None)

    def run_sql_query(self, query: str, *args, **kwargs):
        if not self._enable_run_sql:
            raise RuntimeError(
                "run_sql_query disabled. Set enable_run_sql_query: true in "
                "config/tools/database.yaml to opt in (read-only SELECT enforced)."
            )
        if self._run_sql_raw is None:
            raise RuntimeError("Underlying SQLTools.run_sql_query unavailable")
        _assert_read_only_sql(query)
        return self._run_sql_raw(query, *args, **kwargs)
