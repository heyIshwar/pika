from functools import lru_cache

from pika.infra.db import DATABASE_URL


@lru_cache(maxsize=1)
def get_storage():
    """Return Agno DB adapter (SQLite default, MySQL optional)."""
    if DATABASE_URL.startswith("sqlite"):
        from agno.db.sqlite import SqliteDb

        return SqliteDb(db_url=DATABASE_URL)
    if DATABASE_URL.startswith("mysql"):
        from agno.db.mysql import MySQLDb

        return MySQLDb(db_url=DATABASE_URL)
    raise ValueError(f"Unsupported DATABASE_URL: {DATABASE_URL}")


get_db = get_storage
