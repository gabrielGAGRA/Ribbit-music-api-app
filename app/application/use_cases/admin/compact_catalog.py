"""Use case for triggering compaction of GCS catalog deltas into the base file."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort


@dataclass(slots=True, frozen=True, kw_only=True)
class CompactCatalogResult:
    """Summary of catalog compaction execution."""

    new_version: int
    message: str


@dataclass(slots=True, frozen=True)
class CompactCatalogUseCase:
    """Consolidates remote catalog deltas into the canonical base Parquet file."""

    catalog_file_port: TrackCatalogFilePort
    audit_log_repo: AuditLogRepositoryPort | None = None

    def execute(self) -> CompactCatalogResult:
        new_version = self.catalog_file_port.compact_catalog()
        if self.audit_log_repo is not None:
            self.audit_log_repo.log_event(
                event=f"catalog.compacted.v{new_version}",
                status="success",
            )
        return CompactCatalogResult(
            new_version=new_version,
            message=f"Catalog compacted successfully. Published version {new_version}.",
        )


__all__ = ["CompactCatalogResult", "CompactCatalogUseCase"]
