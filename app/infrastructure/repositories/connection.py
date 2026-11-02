"""SQLite connection management and row factory utilities."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
lazy from collections.abc import Generator

DEFAULT_DATABASE_PATH = "local.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def create_connection(database_path: str = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Creates a new SQLite connection with foreign keys enabled and Row factory configured."""
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor]:
    """Context manager executing block inside an explicit transaction."""
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


__all__ = [
    "DEFAULT_DATABASE_PATH",
    "SCHEMA_PATH",
    "create_connection",
    "transaction",
]
