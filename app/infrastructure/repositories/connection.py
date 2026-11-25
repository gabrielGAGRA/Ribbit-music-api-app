"""SQLite connection management and row factory utilities."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any
lazy from collections.abc import Generator

DEFAULT_DATABASE_PATH = "local.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _open_raw_connection(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    if database_path != ":memory:" and not database_path.startswith("file:"):
        try:
            mode_row = conn.execute("PRAGMA journal_mode;").fetchone()
            if mode_row is None or str(mode_row[0]).lower() != "wal":
                conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            pass
    return conn


class ThreadLocalConnection:
    """Thread-local proxy managing an independent sqlite3.Connection per thread."""

    def __init__(self, database_path: str) -> None:
        object.__setattr__(self, "_database_path", database_path)
        object.__setattr__(self, "_local", threading.local())
        object.__setattr__(self, "_lock", threading.Lock())
        object.__setattr__(self, "_connections", set())
        object.__setattr__(self, "_registered_functions", [])
        object.__setattr__(self, "_closed", False)

    @property
    def current_connection(self) -> sqlite3.Connection:
        """Return the sqlite3.Connection bound to the current thread, opening it if needed."""
        with self._lock:
            if self._closed:
                raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = _open_raw_connection(self._database_path)
            with self._lock:
                if self._closed:
                    conn.close()
                    raise sqlite3.ProgrammingError(
                        "Cannot operate on a closed database."
                    )
                for name, narg, func, args, kwargs in self._registered_functions:
                    conn.create_function(name, narg, func, *args, **kwargs)
                self._connections.add(conn)
            self._local.conn = conn
        return conn

    @property
    def row_factory(self) -> Any:
        return self.current_connection.row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        self.current_connection.row_factory = value

    def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
        return self.current_connection.execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters: Any) -> sqlite3.Cursor:
        return self.current_connection.executemany(sql, seq_of_parameters)

    def executescript(self, sql_script: str) -> sqlite3.Cursor:
        return self.current_connection.executescript(sql_script)

    def commit(self) -> None:
        self.current_connection.commit()

    def rollback(self) -> None:
        self.current_connection.rollback()

    def cursor(self) -> sqlite3.Cursor:
        return self.current_connection.cursor()

    def close(self) -> None:
        """Close all per-thread connections opened by this wrapper."""
        with self._lock:
            object.__setattr__(self, "_closed", True)
            connections = list(self._connections)
            self._connections.clear()
            if hasattr(self._local, "conn"):
                delattr(self._local, "conn")
        for conn in connections:
            conn.close()

    def create_function(
        self, name: str, narg: int, func: Any, *args: Any, **kwargs: Any
    ) -> None:
        """Register a SQLite UDF on all existing and future thread connections."""
        with self._lock:
            if self._closed:
                raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
            self._registered_functions.append((name, narg, func, args, kwargs))
            existing = list(self._connections)
        for conn in existing:
            conn.create_function(name, narg, func, *args, **kwargs)

    def __enter__(self) -> ThreadLocalConnection:
        self.current_connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        return self.current_connection.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.current_connection, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self.current_connection, name, value)


def create_connection(
    database_path: str = DEFAULT_DATABASE_PATH,
    *,
    thread_safe: bool = True,
) -> sqlite3.Connection:
    """Create a configured SQLite connection with foreign keys, busy timeout, and WAL enabled."""
    if (
        thread_safe
        and database_path != ":memory:"
        and not database_path.startswith("file:")
    ):
        wrapper = ThreadLocalConnection(database_path)
        _ = wrapper.current_connection
        return wrapper  # type: ignore[return-value]
    return _open_raw_connection(database_path)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor]:
    """Context manager executing block inside an explicit immediate transaction."""
    cursor = conn.cursor()
    nested = conn.in_transaction
    savepoint = f"sp_tx_{id(cursor)}"
    try:
        if nested:
            cursor.execute(f"SAVEPOINT {savepoint}")
        else:
            conn.execute("BEGIN IMMEDIATE;")
        yield cursor
        if nested:
            cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        else:
            conn.commit()
    except Exception:
        if nested:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        else:
            conn.rollback()
        raise
    finally:
        cursor.close()


__all__ = [
    "DEFAULT_DATABASE_PATH",
    "SCHEMA_PATH",
    "ThreadLocalConnection",
    "create_connection",
    "transaction",
]
