"""Use case for synchronizing local database with remote GCS catalog version."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort
lazy from app.application.use_cases.admin.ingest_tracks import (
    IngestTracksFromCatalogUseCase,
    IngestTracksResult,
)


@dataclass(slots=True, frozen=True, kw_only=True)
class SyncCatalogVersionResult:
    """Result of catalog version synchronization."""

    synced: bool
    version: int
    message: str
    ingest_result: IngestTracksResult | None = None


@dataclass(slots=True)
class SyncCatalogVersionUseCase:
    """Checks remote catalog version and updates local tracks DB when a new version is published."""

    catalog_file_port: TrackCatalogFilePort
    ingest_use_case: IngestTracksFromCatalogUseCase
    audit_log_repo: AuditLogRepositoryPort | None = None
    _last_synced_version: int = 0

    def execute(self, *, force: bool = False) -> SyncCatalogVersionResult:
        info = self.catalog_file_port.get_catalog_version()
        if not force and info.version <= self._last_synced_version:
            return SyncCatalogVersionResult(
                synced=False,
                version=info.version,
                message=f"Local catalog is up to date (version {self._last_synced_version}).",
            )

        ingest_res = self.ingest_use_case.execute()
        self._last_synced_version = info.version

        if self.audit_log_repo is not None:
            self.audit_log_repo.log_event(
                event=f"catalog.synced.v{info.version}",
                status="success",
            )

        return SyncCatalogVersionResult(
            synced=True,
            version=info.version,
            message=f"Local catalog updated to version {info.version}.",
            ingest_result=ingest_res,
        )


__all__ = ["SyncCatalogVersionResult", "SyncCatalogVersionUseCase"]
