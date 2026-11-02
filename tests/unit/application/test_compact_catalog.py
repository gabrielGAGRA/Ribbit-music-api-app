"""Unit tests for CompactCatalogUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories import AuditLogRepositoryPort
from app.application.ports.services import TrackCatalogFilePort
from app.application.use_cases.admin.compact_catalog import CompactCatalogUseCase
from app.domain.exceptions import ExternalServiceError


def test_compact_catalog_executes_and_logs_audit() -> None:
    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.compact_catalog.return_value = 5

    mock_audit = MagicMock(spec=AuditLogRepositoryPort)

    use_case = CompactCatalogUseCase(
        catalog_file_port=mock_catalog,
        audit_log_repo=mock_audit,
    )

    result = use_case.execute()

    assert result.new_version == 5
    assert "version 5" in result.message
    mock_catalog.compact_catalog.assert_called_once()
    mock_audit.log_event.assert_called_once_with(
        event="catalog.compacted.v5",
        status="success",
    )


def test_compact_catalog_propagates_error() -> None:
    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.compact_catalog.side_effect = ExternalServiceError(
        "GCS error", service_name="GCP_GCS"
    )

    use_case = CompactCatalogUseCase(catalog_file_port=mock_catalog)

    with pytest.raises(ExternalServiceError) as exc_info:
        use_case.execute()

    assert "GCS error" in str(exc_info.value)
