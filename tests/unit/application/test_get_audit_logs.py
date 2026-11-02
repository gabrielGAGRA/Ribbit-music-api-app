"""Unit tests for GetAuditLogsUseCase."""

from unittest.mock import MagicMock

from app.application.dtos.admin_dtos import AuditLogEntryResult
from app.application.use_cases.admin.get_audit_logs import GetAuditLogsUseCase


def test_get_audit_logs_initializes_when_empty() -> None:
    audit_repo = MagicMock()
    # First call returns empty, second call returns initialized logs
    initialized_entries = [
        AuditLogEntryResult(event="SYSTEM_INITIALIZED", status="OK"),
        AuditLogEntryResult(event="CATALOG_AUDIT", status="OK"),
    ]
    audit_repo.list_all.side_effect = [[], initialized_entries]

    use_case = GetAuditLogsUseCase(audit_log_repo=audit_repo)
    result = use_case.execute()

    assert result == initialized_entries
    audit_repo.log_event.assert_any_call("SYSTEM_INITIALIZED", "OK")
    audit_repo.log_event.assert_any_call("CATALOG_AUDIT", "OK")
    assert audit_repo.log_event.call_count == 2


def test_get_audit_logs_returns_existing_without_reinitialization() -> None:
    existing_entries = [
        AuditLogEntryResult(event="USER_BANNED", status="SUCCESS"),
    ]
    audit_repo = MagicMock()
    audit_repo.list_all.return_value = existing_entries

    use_case = GetAuditLogsUseCase(audit_log_repo=audit_repo)
    result = use_case.execute()

    assert result == existing_entries
    audit_repo.log_event.assert_not_called()
