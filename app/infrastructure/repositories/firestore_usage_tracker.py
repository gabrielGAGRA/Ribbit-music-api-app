"""Persistent usage tracker for Firestore operations and synced-table SQLite activity."""

import contextlib
import re
import threading
from datetime import UTC, datetime
lazy import sqlite3

lazy from app.domain.services import FirestoreUsageMetrics

_IGNORED_PREFIX_RE = re.compile(
    r"^\s*(?:PRAGMA|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|CREATE|ALTER|DROP)\b",
    re.IGNORECASE,
)
_SYNCED_TABLE_RE = re.compile(
    r"\b(?:users|plans|platform_cost_settings|reviews|review_likes|playlists|"
    r"playlist_images|playlist_tracks|interactions|jams|jam_queue_items|"
    r"track_accesses|audit_logs)\b",
    re.IGNORECASE,
)
_SQL_VERB_RE = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|REPLACE|DELETE)\b",
    re.IGNORECASE,
)


class FirestoreUsageTracker:
    """Buffers Firestore read/write/delete/egress counters and persists them to SQLite."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, list[int]] = {}

    @staticmethod
    def _today_key() -> str:
        return datetime.now(UTC).date().isoformat()

    def record(
        self,
        *,
        reads: int = 0,
        writes: int = 0,
        deletes: int = 0,
        egress_bytes: int = 0,
    ) -> None:
        """Records Firestore usage increments in memory under a thread lock."""
        add_r = max(0, reads)
        add_w = max(0, writes)
        add_d = max(0, deletes)
        add_e = max(0, egress_bytes)
        if not (add_r or add_w or add_d or add_e):
            return
        day_key = self._today_key()
        with self._lock:
            bucket = self._pending.get(day_key)
            if bucket is None:
                self._pending[day_key] = [add_r, add_w, add_d, add_e]
            else:
                bucket[0] += add_r
                bucket[1] += add_w
                bucket[2] += add_d
                bucket[3] += add_e

    def record_sql_statement(self, sql: str) -> None:
        """SQLite trace callback estimating synced-collection activity in SQLite-only mode."""
        if not sql or _IGNORED_PREFIX_RE.match(sql):
            return
        lower_sql = sql.lower()
        if "sqlite_master" in lower_sql or "firestore_usage_counters" in lower_sql:
            return
        if not _SYNCED_TABLE_RE.search(sql):
            return
        verb_match = _SQL_VERB_RE.match(sql)
        if verb_match is None:
            return
        verb = verb_match.group(1).upper()
        if verb == "SELECT":
            self.record(reads=1, egress_bytes=512)
        elif verb == "DELETE":
            self.record(deletes=1)
        else:
            self.record(writes=1, egress_bytes=max(256, len(sql.encode("utf-8"))))

    def _restore_pending(self, batch: dict[str, list[int]]) -> None:
        if not batch:
            return
        with self._lock:
            for day_key, counts in batch.items():
                bucket = self._pending.get(day_key)
                if bucket is None:
                    self._pending[day_key] = list(counts)
                else:
                    for idx in range(4):
                        bucket[idx] += counts[idx]

    def flush(self, conn: sqlite3.Connection) -> None:
        """Persists buffered usage increments to SQLite when no transaction is open."""
        if conn.in_transaction:
            return
        with self._lock:
            if not self._pending:
                return
            batch = self._pending
            self._pending = {}

        try:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'firestore_usage_counters'"
            ).fetchone()
            if not table_exists:
                self._restore_pending(batch)
                return
            now_iso = datetime.now(UTC).isoformat()
            for day_key, (reads, writes, deletes, egress) in batch.items():
                conn.execute(
                    """
                    INSERT INTO firestore_usage_counters (
                        metric_date, reads_count, writes_count, deletes_count,
                        egress_bytes, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(metric_date) DO UPDATE SET
                        reads_count = reads_count + excluded.reads_count,
                        writes_count = writes_count + excluded.writes_count,
                        deletes_count = deletes_count + excluded.deletes_count,
                        egress_bytes = egress_bytes + excluded.egress_bytes,
                        updated_at = excluded.updated_at
                    """,
                    (day_key, reads, writes, deletes, egress, now_iso),
                )
            conn.commit()
        except sqlite3.Error:
            self._restore_pending(batch)

    def get_usage_metrics(self, conn: sqlite3.Connection) -> FirestoreUsageMetrics:
        """Flushes pending deltas and returns today's ops, stored size, and monthly egress."""
        self.flush(conn)
        today_key = self._today_key()
        month_prefix = f"{today_key[:7]}-"

        reads_today = 0
        writes_today = 0
        deletes_today = 0
        egress_month = 0
        with contextlib.suppress(sqlite3.Error):
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'firestore_usage_counters'"
            ).fetchone()
            if table_exists:
                day_row = conn.execute(
                    """
                    SELECT reads_count, writes_count, deletes_count
                    FROM firestore_usage_counters
                    WHERE metric_date = ?
                    """,
                    (today_key,),
                ).fetchone()
                if day_row is not None:
                    reads_today = int(day_row[0])
                    writes_today = int(day_row[1])
                    deletes_today = int(day_row[2])
                month_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(egress_bytes), 0)
                    FROM firestore_usage_counters
                    WHERE metric_date LIKE ?
                    """,
                    (f"{month_prefix}%",),
                ).fetchone()
                if month_row is not None:
                    egress_month = int(month_row[0])

        with self._lock:
            for day_key, (
                p_reads,
                p_writes,
                p_deletes,
                p_egress,
            ) in self._pending.items():
                if day_key == today_key:
                    reads_today += p_reads
                    writes_today += p_writes
                    deletes_today += p_deletes
                if day_key.startswith(month_prefix):
                    egress_month += p_egress

        stored_bytes = 0
        with contextlib.suppress(sqlite3.Error):
            page_count_row = conn.execute("PRAGMA page_count;").fetchone()
            page_size_row = conn.execute("PRAGMA page_size;").fetchone()
            page_count = int(page_count_row[0]) if page_count_row else 0
            page_size = int(page_size_row[0]) if page_size_row else 0
            stored_bytes = max(0, page_count * page_size)

        return FirestoreUsageMetrics(
            reads_today=reads_today,
            writes_today=writes_today,
            deletes_today=deletes_today,
            stored_bytes=stored_bytes,
            egress_bytes_month=egress_month,
        )


__all__ = ["FirestoreUsageTracker"]
