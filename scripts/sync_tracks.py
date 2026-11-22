"""CLI script to synchronize and ingest tracks from a Cloud Storage Parquet file."""

import argparse
import sys

from app.application.use_cases.admin.compact_catalog import CompactCatalogUseCase
from app.application.use_cases.admin.ingest_tracks import (
    IngestTracksFromCatalogUseCase,
)
from app.application.use_cases.admin.sync_catalog_version import (
    SyncCatalogVersionUseCase,
)
from app.config import load_settings
from app.infrastructure.adapters import GCSTrackCatalogAdapter
from app.infrastructure.repositories import (
    SQLiteAuditLogRepository,
    SQLiteTrackRepository,
    create_connection,
)
from app.infrastructure.repositories.seed import migrate_additive_columns
from app.infrastructure.telemetry import (
    configure_logging,
    log_operational_event,
)


def run_sync(argv: list[str] | None = None) -> int:
    """Executes the Cloud Storage Parquet tracks ingestion or compaction."""
    parser = argparse.ArgumentParser(description="Sync or compact tracks from GCS.")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact remote micro-deltas into base Parquet file and increment version.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force ingestion regardless of remote catalog version.",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    logger = configure_logging(level=settings.log_level)

    if not settings.gcs_bucket_name:
        log_operational_event(
            logger,
            event="catalog.sync.missing_bucket",
            status="failure",
            message="GCS_BUCKET_NAME is not set. Please set GCS_BUCKET_NAME in your environment or .env.",
        )
        return 1

    catalog_adapter = GCSTrackCatalogAdapter(
        bucket_name=settings.gcs_bucket_name,
        file_path=settings.gcs_tracks_file_path,
    )

    conn = create_connection(settings.database_path)
    try:
        migrate_additive_columns(conn)
        audit_log_repo = SQLiteAuditLogRepository(conn)

        if args.compact:
            log_operational_event(
                logger,
                event="catalog.compact.start",
                status="start",
                message="Starting catalog compaction",
                bucket=settings.gcs_bucket_name,
            )
            try:
                compact_use_case = CompactCatalogUseCase(
                    catalog_file_port=catalog_adapter,
                    audit_log_repo=audit_log_repo,
                )
                res = compact_use_case.execute()
                log_operational_event(
                    logger,
                    event="catalog.compact.success",
                    status="success",
                    message=res.message,
                    new_version=res.new_version,
                )
            except Exception as exc:  # noqa: BLE001 - CLI process boundary
                log_operational_event(
                    logger,
                    event="catalog.compact.failure",
                    status="failure",
                    message="Catalog compaction failed.",
                    exc_info=exc,
                )
                return 1
            else:
                return 0

        log_operational_event(
            logger,
            event="catalog.sync.start",
            status="start",
            message="Starting tracks sync from GCS bucket",
            bucket=settings.gcs_bucket_name,
            file_path=settings.gcs_tracks_file_path,
        )

        track_repo = SQLiteTrackRepository(conn)
        ingest_use_case = IngestTracksFromCatalogUseCase(
            track_repo=track_repo,
            catalog_file_port=catalog_adapter,
        )
        sync_use_case = SyncCatalogVersionUseCase(
            catalog_file_port=catalog_adapter,
            ingest_use_case=ingest_use_case,
            audit_log_repo=audit_log_repo,
        )

        result = sync_use_case.execute(force=args.force)
        log_operational_event(
            logger,
            event="catalog.sync.success",
            status="success",
            message=result.message,
            synced=result.synced,
            version=result.version,
            total_processed=(
                result.ingest_result.total_processed
                if result.ingest_result is not None
                else 0
            ),
            inserted=(
                result.ingest_result.inserted if result.ingest_result is not None else 0
            ),
            updated=(
                result.ingest_result.updated if result.ingest_result is not None else 0
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI process boundary
        log_operational_event(
            logger,
            event="catalog.sync.failure",
            status="failure",
            message="Failed to sync tracks from GCP.",
            exc_info=exc,
        )
        return 1
    else:
        return 0
    finally:
        conn.close()


__all__ = ["run_sync"]

if __name__ == "__main__":
    sys.exit(run_sync())
