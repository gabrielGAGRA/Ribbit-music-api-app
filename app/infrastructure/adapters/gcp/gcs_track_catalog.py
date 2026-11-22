"""Adapter for fetching and compacting catalog tracks from a GCP Cloud Storage Parquet file."""

import contextlib
import json
import logging
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
lazy from collections.abc import Iterator, Sequence

import pyarrow as pa
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage

from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    CatalogVersionInfo,
    TrackCatalogFilePort,
)
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.gcp import catalog_parquet

logger = logging.getLogger("app.infrastructure.gcs_track_catalog")


class GCSTrackCatalogAdapter(TrackCatalogFilePort):
    """GCP Cloud Storage adapter reading and updating music catalog tracks."""

    def __init__(
        self,
        *,
        bucket_name: str,
        file_path: str = "Songs/songs_final.parquet",
        storage_client: storage.Client | None = None,
        timeout: float = 30.0,
        max_tracks: int | None = None,
    ) -> None:
        self._bucket_name = bucket_name
        self._file_path = file_path
        self._storage_client = storage_client
        self._timeout = timeout
        self._max_tracks = max_tracks

        if "/" in file_path:
            parent_dir = file_path.rsplit("/", 1)[0]
            self._delta_prefix = f"{parent_dir}/deltas"
            self._version_path = f"{parent_dir}/catalog_version.json"
        else:
            self._delta_prefix = "deltas"
            self._version_path = "catalog_version.json"

    def _get_client(self) -> storage.Client:
        if self._storage_client is not None:
            return self._storage_client
        try:
            self._storage_client = storage.Client()
        except Exception as exc:
            logger.exception("Failed to initialize GCP Cloud Storage client")
            raise ExternalServiceError(
                "Failed to initialize cloud storage client.",
                service_name="GCP_GCS",
            ) from exc
        else:
            return self._storage_client

    def fetch_tracks(self) -> Sequence[CatalogSourceTrack]:
        """Downloads the Parquet file from GCS, merging any pending deltas."""
        if not self._bucket_name:
            raise ExternalServiceError(
                "GCS bucket name is not configured.",
                service_name="GCP_GCS",
            )

        client = self._get_client()
        try:
            bucket = client.bucket(self._bucket_name)
            blob = bucket.blob(self._file_path)
            content_bytes = blob.download_as_bytes(timeout=self._timeout)
        except Exception as exc:
            logger.exception(
                "Failed to download '%s' from GCS bucket '%s'",
                self._file_path,
                self._bucket_name,
            )
            raise ExternalServiceError(
                "Failed to download catalog tracks from cloud storage.",
                service_name="GCP_GCS",
            ) from exc

        base_tracks = list(self.parse_parquet_bytes(content_bytes))
        delta_map = self._load_pending_deltas()
        if not delta_map:
            return base_tracks

        merged = [
            catalog_parquet.apply_delta_to_track(t, delta_map) for t in base_tracks
        ]
        existing_sids: set[str] = set()
        existing_keys: set[tuple[str, str]] = set()
        catalog_parquet.record_seen_keys(merged, existing_sids, existing_keys)
        merged.extend(
            catalog_parquet.delta_to_catalog_track(delta)
            for delta in catalog_parquet.iter_new_deltas(
                delta_map, existing_sids, existing_keys
            )
        )
        return merged

    def _download_catalog_to_temp(self, bucket: storage.Bucket) -> Path:
        tmp_path: Path | None = None
        try:
            blob = bucket.blob(self._file_path)
            with tempfile.NamedTemporaryFile(
                suffix=".parquet", delete=False
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
            blob.download_to_filename(str(tmp_path), timeout=max(self._timeout, 300.0))
        except Exception as exc:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
            logger.exception(
                "Failed to download '%s' from GCS bucket '%s'",
                self._file_path,
                self._bucket_name,
            )
            raise ExternalServiceError(
                "Failed to download catalog tracks from cloud storage.",
                service_name="GCP_GCS",
            ) from exc
        else:
            return tmp_path

    def iter_track_batches(
        self, batch_size: int = 50_000
    ) -> Iterator[list[CatalogSourceTrack]]:
        """Streams Parquet row batches from GCS without loading the full table in RAM."""
        if not self._bucket_name:
            raise ExternalServiceError(
                "GCS bucket name is not configured.", service_name="GCP_GCS"
            )

        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        tmp_path = self._download_catalog_to_temp(bucket)

        try:
            delta_map = self._load_pending_deltas()
            existing_sids: set[str] = set()
            existing_keys: set[tuple[str, str]] = set()
            yield from catalog_parquet.iter_parquet_file_batches(
                tmp_path,
                batch_size,
                self._max_tracks,
                delta_map,
                existing_sids,
                existing_keys,
            )
            if delta_map:
                new_tracks = [
                    catalog_parquet.delta_to_catalog_track(delta)
                    for delta in catalog_parquet.iter_new_deltas(
                        delta_map, existing_sids, existing_keys
                    )
                ]
                for start in range(0, len(new_tracks), batch_size):
                    yield new_tracks[start : start + batch_size]
        finally:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)

    def write_track_delta(
        self,
        *,
        title: str,
        artist: str,
        preview_url: str | None = None,
        genre: str | None = None,
        cover_url: str | None = None,
        spotify_id: str | None = None,
        album: str | None = None,
        duration_seconds: int | None = None,
        country: str | None = None,
        release_year: int | None = None,
        explicit: bool | None = None,
        is_deleted: bool | None = None,
        created_at: str | None = None,
    ) -> None:
        """Writes a micro-delta Parquet matching the tracks table schema to remote storage."""
        if not self._bucket_name:
            return

        client = self._get_client()
        try:
            bucket = client.bucket(self._bucket_name)
            parquet_bytes = catalog_parquet.build_delta_parquet_bytes(
                title=title,
                artist=artist,
                preview_url=preview_url,
                genre=genre,
                cover_url=cover_url,
                spotify_id=spotify_id,
                album=album,
                duration_seconds=duration_seconds,
                country=country,
                release_year=release_year,
                explicit=explicit,
                is_deleted=is_deleted,
                created_at=created_at,
            )
            delta_blob_name = (
                f"{self._delta_prefix}/delta_{uuid.uuid4().hex[:12]}.parquet"
            )
            blob = bucket.blob(delta_blob_name)
            blob.upload_from_string(
                parquet_bytes,
                content_type="application/octet-stream",
                timeout=self._timeout,
            )
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to write track delta to GCS bucket '%s'",
                self._bucket_name,
            )
            raise ExternalServiceError(
                "Failed to write track delta to cloud storage.",
                service_name="GCP_GCS",
            ) from exc

    def _delete_delta_blobs(self, blobs: Sequence[storage.Blob]) -> None:
        for b in blobs:
            try:
                b.delete(timeout=self._timeout)
            except (GoogleAPIError, RuntimeError, OSError) as exc:
                logger.warning(
                    "Failed to delete processed delta blob '%s' from GCS bucket '%s': %s",
                    b.name,
                    self._bucket_name,
                    exc,
                )

    def compact_catalog(self) -> int:
        """Consolidates pending deltas into base catalog file, cleanses deltas, bumps version."""
        if not self._bucket_name:
            raise ExternalServiceError(
                "GCS bucket name is not configured.", service_name="GCP_GCS"
            )

        client = self._get_client()
        try:
            bucket = client.bucket(self._bucket_name)
            blobs = list(
                client.list_blobs(self._bucket_name, prefix=self._delta_prefix)
            )
            delta_blobs = [b for b in blobs if b.name.endswith(".parquet")]

            current_version_info = self.get_catalog_version()
            if not delta_blobs:
                return current_version_info.version

            delta_map = self._read_deltas_from_blobs(delta_blobs)
            base_blob = bucket.blob(self._file_path)
            base_bytes = base_blob.download_as_bytes(timeout=self._timeout)
            compacted_bytes = catalog_parquet.compact_parquet_bytes(
                base_bytes, delta_map
            )
            base_blob.upload_from_string(
                compacted_bytes,
                content_type="application/octet-stream",
                timeout=self._timeout,
            )

            self._delete_delta_blobs(delta_blobs)

            new_version = current_version_info.version + 1
            version_data = {
                "version": new_version,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            version_blob = bucket.blob(self._version_path)
            version_blob.upload_from_string(
                json.dumps(version_data),
                content_type="application/json",
                timeout=self._timeout,
            )
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to compact catalog in GCS bucket '%s'",
                self._bucket_name,
            )
            raise ExternalServiceError(
                "Failed to compact catalog in cloud storage.",
                service_name="GCP_GCS",
            ) from exc
        else:
            return new_version

    def get_catalog_version(self) -> CatalogVersionInfo:
        """Reads the remote catalog version sentinel."""
        if not self._bucket_name:
            raise ExternalServiceError(
                "GCS bucket name is not configured.", service_name="GCP_GCS"
            )

        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._version_path)

        try:
            if not blob.exists(timeout=self._timeout):
                return CatalogVersionInfo(
                    version=1, updated_at=datetime.now(UTC).isoformat()
                )
            raw_text = blob.download_as_text(timeout=self._timeout)
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to read catalog version from GCS bucket '%s'",
                self._bucket_name,
            )
            raise ExternalServiceError(
                "Failed to read catalog version from cloud storage.",
                service_name="GCP_GCS",
            ) from exc

        try:
            data = json.loads(raw_text)
            return CatalogVersionInfo(
                version=int(data.get("version", 1)),
                updated_at=str(data.get("updated_at", datetime.now(UTC).isoformat())),
            )
        except json.JSONDecodeError, ValueError, KeyError:
            return CatalogVersionInfo(
                version=1, updated_at=datetime.now(UTC).isoformat()
            )

    def _load_pending_deltas(
        self,
    ) -> dict[str | tuple[str, str], catalog_parquet._TrackDeltaItem]:
        try:
            client = (
                self._storage_client
                if self._storage_client is not None
                else self._get_client()
            )
            blobs = list(
                client.list_blobs(self._bucket_name, prefix=self._delta_prefix)
            )
            delta_blobs = [b for b in blobs if b.name.endswith(".parquet")]
            return self._read_deltas_from_blobs(delta_blobs, ignore_blob_errors=True)
        except (GoogleAPIError, OSError) as exc:
            logger.warning("Failed to load pending catalog deltas: %s", exc)
            return {}

    def _download_delta_bytes_batch(
        self, blobs: Sequence[storage.Blob], *, ignore_blob_errors: bool = False
    ) -> list[bytes | None]:
        def _download(blob: storage.Blob) -> bytes | None:
            try:
                return blob.download_as_bytes(timeout=self._timeout)
            except (pa.ArrowInvalid, ValueError, KeyError) as exc:
                logger.debug("Skipping unreadable delta blob %s: %s", blob.name, exc)
                return None
            except (GoogleAPIError, OSError, RuntimeError) as exc:
                if not ignore_blob_errors:
                    raise
                logger.warning(
                    "Skipping inaccessible delta blob %s: %s", blob.name, exc
                )
                return None

        if len(blobs) <= 1:
            return [_download(b) for b in blobs]
        with ThreadPoolExecutor(max_workers=min(16, len(blobs))) as executor:
            return list(executor.map(_download, blobs))

    def _read_deltas_from_blobs(
        self, blobs: Sequence[storage.Blob], *, ignore_blob_errors: bool = False
    ) -> dict[str | tuple[str, str], catalog_parquet._TrackDeltaItem]:
        contents = self._download_delta_bytes_batch(
            blobs, ignore_blob_errors=ignore_blob_errors
        )
        return catalog_parquet.read_deltas_from_bytes(
            [(b.name, content) for b, content in zip(blobs, contents, strict=True)]
        )

    def parse_parquet_bytes(self, content_bytes: bytes) -> Sequence[CatalogSourceTrack]:
        """Parses in-memory Parquet file bytes into CatalogSourceTrack objects."""
        return catalog_parquet.parse_parquet_bytes(
            content_bytes, file_path=self._file_path
        )

    @staticmethod
    def _parse_records(records: Sequence[dict[str, Any]]) -> list[CatalogSourceTrack]:
        return catalog_parquet._parse_records(records)


__all__ = ["GCSTrackCatalogAdapter"]
