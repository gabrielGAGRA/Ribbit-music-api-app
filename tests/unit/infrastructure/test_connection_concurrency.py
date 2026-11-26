"""Unit tests verifying SQLite concurrency, pragmas, and lazy app import."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
lazy from pathlib import Path

import pytest

from app.infrastructure.repositories.connection import (
    ThreadLocalConnection,
    create_connection,
)


def test_create_connection_applies_pragmas_and_thread_local_wrapper(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test_concurrency.db"
    conn = create_connection(str(db_file), thread_safe=True)

    assert isinstance(conn, ThreadLocalConnection)
    row_fk = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert row_fk[0] == 1

    row_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()
    assert row_timeout[0] == 30000

    row_journal = conn.execute("PRAGMA journal_mode;").fetchone()
    assert row_journal[0].upper() == "WAL"

    conn.close()


def test_thread_local_connection_uses_distinct_connections_per_thread(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "distinct_connections.db"
    conn = create_connection(str(db_file), thread_safe=True)
    assert isinstance(conn, ThreadLocalConnection)

    main_raw = conn.current_connection
    seen_ids: set[int] = {id(main_raw)}
    lock = threading.Lock()

    def worker() -> None:
        raw = conn.current_connection
        assert isinstance(raw, sqlite3.Connection)
        with lock:
            seen_ids.add(id(raw))

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker) for _ in range(4)]
        for future in futures:
            future.result()

    assert len(seen_ids) == 5
    conn.close()


def test_thread_local_connection_propagates_create_function_across_threads(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "udf_threads.db"
    conn = create_connection(str(db_file), thread_safe=True)

    def _double_val(val: int) -> int:
        return val * 2

    conn.create_function("DOUBLE_VAL", 1, _double_val)

    def worker(val: int) -> int:
        row = conn.execute("SELECT DOUBLE_VAL(?);", (val,)).fetchone()
        return int(row[0])

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(1, 5)))

    assert sorted(results) == [2, 4, 6, 8]
    conn.close()


def test_thread_local_connection_concurrent_writes(tmp_path: Path) -> None:
    db_file = tmp_path / "concurrent_writes.db"
    conn = create_connection(str(db_file), thread_safe=True)

    conn.execute(
        "CREATE TABLE test_counter (id INTEGER PRIMARY KEY AUTOINCREMENT, val INTEGER);"
    )
    conn.commit()

    def worker(worker_id: int) -> None:
        for i in range(25):
            conn.execute(
                "INSERT INTO test_counter (val) VALUES (?);", (worker_id * 100 + i,)
            )
            conn.commit()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, t) for t in range(4)]
        for future in futures:
            future.result()

    count_row = conn.execute("SELECT count(*) FROM test_counter;").fetchone()
    assert count_row[0] == 100
    conn.close()


def test_transaction_context_manager_concurrency(tmp_path: Path) -> None:
    import time

    from app.infrastructure.repositories.connection import transaction

    db_file = tmp_path / "concurrent_transactions.db"
    conn = create_connection(str(db_file), thread_safe=True)

    conn.execute(
        "CREATE TABLE test_tx (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT, val INTEGER);"
    )
    conn.commit()

    def tx_worker(worker_id: int) -> None:
        for i in range(15):
            with transaction(conn) as cur:
                cur.execute(
                    "INSERT INTO test_tx (tag, val) VALUES (?, ?);",
                    (f"worker_{worker_id}", i),
                )
                time.sleep(0.001)
                cur.execute(
                    "UPDATE test_tx SET val = val + 10 WHERE tag = ? AND val = ?;",
                    (f"worker_{worker_id}", i),
                )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(tx_worker, w) for w in range(4)]
        for future in futures:
            future.result()

    total = conn.execute("SELECT count(*) FROM test_tx;").fetchone()[0]
    assert total == 60
    conn.close()


def test_app_main_attribute_access() -> None:
    import app.main as main_mod

    assert main_mod.app is not None
    assert main_mod.app.title == "Ribbit Platform API"


def test_thread_local_connection_propagates_sql_operational_error(
    tmp_path: Path,
) -> None:
    mem_conn = create_connection(":memory:", thread_safe=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            mem_conn.execute("SELECT * FROM nonexistent_table_xyz;")
    finally:
        mem_conn.close()

    file_conn = create_connection(str(tmp_path / "err.db"), thread_safe=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            file_conn.execute("SELECT * FROM nonexistent_table_xyz;")
    finally:
        file_conn.close()


def test_thread_local_connection_raises_programming_error_after_close(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "closed.db"
    conn = create_connection(str(db_file), thread_safe=True)
    conn.execute("SELECT 1;")
    conn.close()

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1;")

    def worker() -> None:
        conn.execute("SELECT 1;")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(worker)
        with pytest.raises(sqlite3.ProgrammingError):
            future.result()
