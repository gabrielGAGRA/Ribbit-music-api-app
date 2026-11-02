"""CLI script to synchronize and ingest tracks from a GCP Cloud Storage Parquet file."""

import argparse
import logging
import sys

from app.application.use_cases.admin.compact_catalog import CompactCatalogUseCase
from app.application.use_cases.admin.ingest_tracks import (
    IngestTracksFromCatalogUseCase,
)
from app.application.use_cases.admin.sync_catalog_version import (
    SyncCatalogVersionUseCase,
)
from app.config import load_settings
from app.infrastructure.adapters.gcp import GCSTrackCatalogAdapter
from app.infrastructure.repositories.connection import create_connection
from app.infrastructure.repositories.seed import migrate_additive_columns
from app.infrastructure.repositories.track_repository import SQLiteTrackRepository

logger = logging.getLogger("gcp.sync_tracks")


def run_sync(argv: list[str] | None = None) -> int:
    """Executes the GCP Parquet tracks ingestion or compaction."""
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

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    settings = load_settings()

    if not settings.gcs_bucket_name:
        logger.error(
            "GCS_BUCKET_NAME is not set. Please set GCS_BUCKET_NAME in your environment or .env."
        )
        return 1

    catalog_adapter = GCSTrackCatalogAdapter(
        bucket_name=settings.gcs_bucket_name,
        file_path=settings.gcs_tracks_file_path,
    )

    if args.compact:
        logger.info(
            "Starting catalog compaction on bucket '%s'...",
            settings.gcs_bucket_name,
        )
        try:
            compact_use_case = CompactCatalogUseCase(catalog_file_port=catalog_adapter)
            res = compact_use_case.execute()
            logger.info(res.message)
        except Exception:
            logger.exception("Catalog compaction failed.")
            return 1
        else:
            return 0

    logger.info(
        "Starting tracks sync from GCS bucket '%s' (file: '%s')...",
        settings.gcs_bucket_name,
        settings.gcs_tracks_file_path,
    )

    conn = create_connection(settings.database_path)
    try:
        migrate_additive_columns(conn)
        track_repo = SQLiteTrackRepository(conn)
        ingest_use_case = IngestTracksFromCatalogUseCase(
            track_repo=track_repo,
            catalog_file_port=catalog_adapter,
        )
        sync_use_case = SyncCatalogVersionUseCase(
            catalog_file_port=catalog_adapter,
            ingest_use_case=ingest_use_case,
        )

        result = sync_use_case.execute(force=args.force)
        logger.info(result.message)
        if result.ingest_result is not None:
            logger.info(
                "Ingestion stats: %d tracks processed (%d inserted, %d updated).",
                result.ingest_result.total_processed,
                result.ingest_result.inserted,
                result.ingest_result.updated,
            )
    except Exception:
        logger.exception("Failed to sync tracks from GCP.")
        return 1
    else:
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(run_sync())
