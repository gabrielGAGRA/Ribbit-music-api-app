"""Unit tests verifying SQLite concurrency, pragmas, and lazy app import."""

import threading

from app.infrastructure.repositories.connection import (
    ThreadSafeConnection,
    create_connection,
)


def test_create_connection_applies_pragmas_and_thread_safe_wrapper(tmp_path) -> None:
    db_file = tmp_path / "test_concurrency.db"
    conn = create_connection(str(db_file), thread_safe=True)

    assert isinstance(conn, ThreadSafeConnection)
    row_fk = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert row_fk[0] == 1

    row_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()
    assert row_timeout[0] == 5000

    row_journal = conn.execute("PRAGMA journal_mode;").fetchone()
    assert row_journal[0].upper() == "WAL"

    conn.close()


def test_thread_safe_connection_concurrent_writes(tmp_path) -> None:
    db_file = tmp_path / "concurrent_writes.db"
    conn = create_connection(str(db_file), thread_safe=True)

    conn.execute(
        "CREATE TABLE test_counter (id INTEGER PRIMARY KEY AUTOINCREMENT, val INTEGER);"
    )
    conn.commit()

    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(25):
                conn.execute(
                    "INSERT INTO test_counter (val) VALUES (?);", (worker_id * 100 + i,)
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent workers encountered errors: {errors}"

    count_row = conn.execute("SELECT count(*) FROM test_counter;").fetchone()
    assert count_row[0] == 100
    conn.close()


def test_transaction_context_manager_concurrency(tmp_path) -> None:
    import time

    from app.infrastructure.repositories.connection import transaction

    db_file = tmp_path / "concurrent_transactions.db"
    conn = create_connection(str(db_file), thread_safe=True)

    conn.execute(
        "CREATE TABLE test_tx (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT, val INTEGER);"
    )
    conn.commit()

    errors: list[Exception] = []

    def tx_worker(worker_id: int) -> None:
        try:
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
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=tx_worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent transaction workers failed: {errors}"
    total = conn.execute("SELECT count(*) FROM test_tx;").fetchone()[0]
    assert total == 60
    conn.close()


def test_app_main_attribute_access() -> None:
    import app.main as main_mod

    assert main_mod.app is not None
    assert main_mod.app.title == "Ribbit Platform API"
