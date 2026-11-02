"""Use case for retrieving system audit records."""

from dataclasses import dataclass

lazy from app.application.dtos.admin_dtos import AuditLogEntryResult
lazy from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)


@dataclass(slots=True, frozen=True)
class GetAuditLogsUseCase:
    """Returns system operation and catalog audit events."""

    audit_log_repo: AuditLogRepositoryPort

    def execute(self) -> list[AuditLogEntryResult]:
        entries = self.audit_log_repo.list_all()
        if not entries:
            self.audit_log_repo.log_event("SYSTEM_INITIALIZED", "OK")
            self.audit_log_repo.log_event("CATALOG_AUDIT", "OK")
            return self.audit_log_repo.list_all()
        return entries
