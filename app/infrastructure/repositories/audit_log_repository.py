"""SQLite implementation of the audit log persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.dtos.admin_dtos import AuditLogEntryResult
from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
from app.infrastructure.repositories.connection import transaction


class SQLiteAuditLogRepository(AuditLogRepositoryPort):
    """SQLite adapter implementing AuditLogRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def log_event(self, event: str, status: str) -> None:
        created_at_str = datetime.now(UTC).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (event, status, created_at)
                VALUES (?, ?, ?)
                """,
                (event, status, created_at_str),
            )

    def list_all(self) -> list[AuditLogEntryResult]:
        cursor = self.conn.execute(
            """
            SELECT event, status FROM audit_logs
            ORDER BY log_id ASC
            """
        )
        rows = cursor.fetchall()
        return [
            AuditLogEntryResult(event=row["event"], status=row["status"])
            for row in rows
        ]

    def has_successful_catalog_sync(self) -> bool:
        cursor = self.conn.execute(
            """
            SELECT 1 FROM audit_logs
            WHERE status = 'success' AND event LIKE 'catalog.synced.v%'
            LIMIT 1
            """
        )
        return cursor.fetchone() is not None


AuditLogRepository = SQLiteAuditLogRepository

__all__ = ["AuditLogRepository", "SQLiteAuditLogRepository"]
