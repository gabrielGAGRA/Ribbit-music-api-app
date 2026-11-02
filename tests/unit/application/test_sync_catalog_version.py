"""Unit tests for SyncCatalogVersionUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories import AuditLogRepositoryPort
from app.application.ports.services import CatalogVersionInfo, TrackCatalogFilePort
from app.application.use_cases.admin.ingest_tracks import (
    IngestTracksFromCatalogUseCase,
    IngestTracksResult,
)
from app.application.use_cases.admin.sync_catalog_version import (
    SyncCatalogVersionUseCase,
)


def test_sync_skips_when_version_unchanged() -> None:
    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.get_catalog_version.return_value = CatalogVersionInfo(
        version=2, updated_at="2026-10-28T12:00:00Z"
    )

    mock_ingest = MagicMock(spec=IngestTracksFromCatalogUseCase)
    mock_audit = MagicMock(spec=AuditLogRepositoryPort)

    use_case = SyncCatalogVersionUseCase(
        catalog_file_port=mock_catalog,
        ingest_use_case=mock_ingest,
        audit_log_repo=mock_audit,
        _last_synced_version=2,
    )

    result = use_case.execute(force=False)

    assert result.synced is False
    assert result.version == 2
    assert "up to date" in result.message
    assert result.ingest_result is None
    mock_ingest.execute.assert_not_called()
    mock_audit.log_event.assert_not_called()


def test_sync_executes_ingest_when_new_version_detected() -> None:
    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.get_catalog_version.return_value = CatalogVersionInfo(
        version=3, updated_at="2026-10-28T13:00:00Z"
    )

    ingest_summary = IngestTracksResult(total_processed=10, inserted=2, updated=8)
    mock_ingest = MagicMock(spec=IngestTracksFromCatalogUseCase)
    mock_ingest.execute.return_value = ingest_summary

    mock_audit = MagicMock(spec=AuditLogRepositoryPort)

    use_case = SyncCatalogVersionUseCase(
        catalog_file_port=mock_catalog,
        ingest_use_case=mock_ingest,
        audit_log_repo=mock_audit,
        _last_synced_version=2,
    )

    result = use_case.execute()

    assert result.synced is True
    assert result.version == 3
    assert result.ingest_result == ingest_summary
    assert "updated to version 3" in result.message
    mock_ingest.execute.assert_called_once()
    mock_audit.log_event.assert_called_once_with(
        event="catalog.synced.v3",
        status="success",
    )


def test_sync_executes_when_forced_even_if_version_matches() -> None:
    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.get_catalog_version.return_value = CatalogVersionInfo(
        version=2, updated_at="2026-10-28T12:00:00Z"
    )

    mock_ingest = MagicMock(spec=IngestTracksFromCatalogUseCase)
    mock_ingest.execute.return_value = IngestTracksResult(
        total_processed=5, inserted=0, updated=5
    )

    use_case = SyncCatalogVersionUseCase(
        catalog_file_port=mock_catalog,
        ingest_use_case=mock_ingest,
        _last_synced_version=2,
    )

    result = use_case.execute(force=True)

    assert result.synced is True
    assert result.version == 2
    mock_ingest.execute.assert_called_once()
