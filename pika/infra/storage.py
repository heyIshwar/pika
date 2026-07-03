import os
from functools import lru_cache

from pika.infra.db import DATABASE_URL


@lru_cache(maxsize=1)
def get_storage():
    """Return Agno DB adapter (SQLite or PostgreSQL)."""
    if DATABASE_URL.startswith("sqlite"):
        from agno.db.sqlite import SqliteDb

        return SqliteDb(db_url=DATABASE_URL)

    if DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres"):
        from agno.db.postgres import PostgresDb

        schema = os.getenv("PIKA_DB_SCHEMA", "pika")
        return PostgresDb(db_url=DATABASE_URL, db_schema=schema)

    raise ValueError(
        f"Unsupported DATABASE_URL scheme: {DATABASE_URL!r}. "
        "Use sqlite:/// or postgresql://"
    )


get_db = get_storage
