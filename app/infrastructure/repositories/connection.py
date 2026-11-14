"""SQLite connection management and row factory utilities."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any
lazy from collections.abc import Generator

DEFAULT_DATABASE_PATH = "local.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class BufferedCursor:
    """Cursor proxy holding pre-fetched rows and execution metadata atomically."""

    __slots__ = ("_rows", "_index", "lastrowid", "rowcount", "description")

    def __init__(
        self,
        rows: list[Any],
        lastrowid: int | None,
        rowcount: int,
        description: Any,
    ) -> None:
        self._rows = rows
        self._index = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.description = description

    def fetchone(self) -> Any:
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self) -> list[Any]:
        remaining = self._rows[self._index :]
        self._index = len(self._rows)
        return remaining

    def fetchmany(self, size: int = 1) -> list[Any]:
        end = min(self._index + size, len(self._rows))
        chunk = self._rows[self._index : end]
        self._index = end
        return chunk

    def close(self) -> None:
        pass

    def __iter__(self) -> Generator[Any]:
        while self._index < len(self._rows):
            row = self.fetchone()
            if row is not None:
                yield row


class ThreadSafeConnection:
    """Thread-safe proxy wrapper around sqlite3.Connection with reentrant locking."""

    __slots__ = ("_conn", "_lock")

    def __init__(self, conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_lock", threading.RLock())

    def execute(self, sql: str, parameters: Any = ()) -> BufferedCursor:
        with self._lock:
            raw_cursor = self._conn.execute(sql, parameters)
            try:
                rows: list[Any] = raw_cursor.fetchall()
            except sqlite3.OperationalError, sqlite3.ProgrammingError:
                rows = []
            return BufferedCursor(
                rows=rows,
                lastrowid=raw_cursor.lastrowid,
                rowcount=raw_cursor.rowcount,
                description=raw_cursor.description,
            )

    def executemany(self, sql: str, seq_of_parameters: Any) -> BufferedCursor:
        with self._lock:
            raw_cursor = self._conn.executemany(sql, seq_of_parameters)
            return BufferedCursor(
                rows=[],
                lastrowid=raw_cursor.lastrowid,
                rowcount=raw_cursor.rowcount,
                description=raw_cursor.description,
            )

    def executescript(self, sql_script: str) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executescript(sql_script)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def cursor(self) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.cursor()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_function(
        self, name: str, narg: int, func: Any, *args: Any, **kwargs: Any
    ) -> None:
        with self._lock:
            self._conn.create_function(name, narg, func, *args, **kwargs)

    def __enter__(self) -> ThreadSafeConnection:
        self._lock.acquire()
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        try:
            return self._conn.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._lock.release()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._conn, name, value)


def create_connection(
    database_path: str = DEFAULT_DATABASE_PATH,
    *,
    thread_safe: bool = True,
) -> sqlite3.Connection:
    """Creates a configured SQLite connection with foreign keys, busy timeout, and WAL enabled."""
    raw_conn = sqlite3.connect(database_path, timeout=30.0, check_same_thread=False)
    raw_conn.row_factory = sqlite3.Row
    raw_conn.execute("PRAGMA foreign_keys = ON;")
    raw_conn.execute("PRAGMA busy_timeout = 30000;")
    if database_path != ":memory:" and not database_path.startswith("file:"):
        try:
            mode_row = raw_conn.execute("PRAGMA journal_mode;").fetchone()
            if mode_row is None or str(mode_row[0]).lower() != "wal":
                raw_conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            pass

    if thread_safe:
        return ThreadSafeConnection(raw_conn)  # type: ignore[return-value]
    return raw_conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor]:
    """Context manager executing block inside an explicit transaction."""
    lock = getattr(conn, "_lock", None)
    if lock is not None:
        lock.acquire()
    try:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    finally:
        if lock is not None:
            lock.release()


__all__ = [
    "DEFAULT_DATABASE_PATH",
    "SCHEMA_PATH",
    "create_connection",
    "transaction",
]
