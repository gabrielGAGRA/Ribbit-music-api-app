"""Persistence port for audit log entries."""

from typing import Protocol, runtime_checkable

lazy from app.application.dtos.admin_dtos import AuditLogEntryResult


@runtime_checkable
class AuditLogRepositoryPort(Protocol):
    def log_event(self, event: str, status: str) -> None: ...

    def list_all(self) -> list[AuditLogEntryResult]: ...
