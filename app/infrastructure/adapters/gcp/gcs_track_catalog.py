"""Adapter for fetching and compacting catalog tracks from a GCP Cloud Storage Parquet file."""

import contextlib
import io
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
lazy from collections.abc import Sequence

import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    CatalogVersionInfo,
    TrackCatalogFilePort,
)
from app.domain.exceptions import ExternalServiceError

logger = logging.getLogger("app.infrastructure.gcs_track_catalog")


@dataclass(slots=True, frozen=True)
class _TrackDeltaItem:
    preview_url: str | None = None
    genre: str | None = None


class GCSTrackCatalogAdapter(TrackCatalogFilePort):
    """GCP Cloud Storage adapter reading and updating music catalog tracks."""

    def __init__(
        self,
        *,
        bucket_name: str,
        file_path: str = "Songs/songs_final.parquet",
        storage_client: storage.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._bucket_name = bucket_name
        self._file_path = file_path
        self._storage_client = storage_client
        self._timeout = timeout

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
            logger.error(  # noqa: TRY400
                "Failed to initialize GCP Cloud Storage client: %s", exc
            )
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
            logger.error(  # noqa: TRY400
                "Failed to download '%s' from GCS bucket '%s': %s",
                self._file_path,
                self._bucket_name,
                exc,
            )
            raise ExternalServiceError(
                "Failed to download catalog tracks from cloud storage.",
                service_name="GCP_GCS",
            ) from exc

        base_tracks = list(self.parse_parquet_bytes(content_bytes))
        delta_map = self._load_pending_deltas(bucket)
        if not delta_map:
            return base_tracks

        return [self._apply_delta_to_track(t, delta_map) for t in base_tracks]

    def write_track_delta(
        self,
        *,
        title: str,
        artist: str,
        preview_url: str | None = None,
        genre: str | None = None,
        spotify_id: str | None = None,
    ) -> None:
        """Writes a lightweight micro-delta file to remote storage for enriched track metadata."""
        if not self._bucket_name:
            return

        client = self._get_client()
        try:
            bucket = client.bucket(self._bucket_name)

            now_iso = datetime.now(UTC).isoformat()
            data: dict[str, list[Any]] = {
                "title": [title],
                "artist": [artist],
                "itunes_preview_url": [preview_url],
                "genre": [genre],
                "spotify_id": [spotify_id],
                "updated_at": [now_iso],
            }
            table = pa.Table.from_pydict(data)
            sink = io.BytesIO()
            pq.write_table(table, sink)
            parquet_bytes = sink.getvalue()

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
            logger.error(  # noqa: TRY400
                "Failed to write track delta to GCS bucket '%s': %s",
                self._bucket_name,
                exc,
            )
            raise ExternalServiceError(
                "Failed to write track delta to cloud storage.",
                service_name="GCP_GCS",
            ) from exc

    def _apply_deltas_to_records(
        self,
        records: list[dict[str, Any]],
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    ) -> list[dict[str, Any]]:
        updated_records: list[dict[str, Any]] = []
        for record in records:
            spotify_id = str(record.get("spotify_id") or "").strip()
            title = str(record.get("title") or "").strip().lower()
            artist = str(record.get("artist") or "").strip().lower()

            delta = delta_map.get(spotify_id) or delta_map.get((title, artist))
            if delta is not None:
                if delta.preview_url:
                    record["itunes_preview_url"] = delta.preview_url
                if delta.genre:
                    record["genre"] = delta.genre
            updated_records.append(record)
        return updated_records

    def _delete_delta_blobs(self, blobs: Sequence[storage.Blob]) -> None:
        for b in blobs:
            try:
                b.delete(timeout=self._timeout)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to delete compacted delta blob %s: %s", b.name, exc
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

            table = pq.read_table(io.BytesIO(base_bytes))
            records = table.to_pylist()
            updated_records = self._apply_deltas_to_records(records, delta_map)

            updated_table = pa.Table.from_pylist(updated_records, schema=table.schema)
            sink = io.BytesIO()
            pq.write_table(updated_table, sink)
            base_blob.upload_from_string(
                sink.getvalue(),
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
            logger.error(  # noqa: TRY400
                "Failed to compact catalog in GCS bucket '%s': %s",
                self._bucket_name,
                exc,
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
            return CatalogVersionInfo(
                version=1, updated_at=datetime.now(UTC).isoformat()
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
            logger.error(  # noqa: TRY400
                "Failed to read catalog version from GCS bucket '%s': %s",
                self._bucket_name,
                exc,
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
        self, bucket: storage.Bucket
    ) -> dict[str | tuple[str, str], _TrackDeltaItem]:
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
            return self._read_deltas_from_blobs(delta_blobs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load pending catalog deltas: %s", exc)
            return {}

    def _read_deltas_from_blobs(
        self, blobs: Sequence[storage.Blob]
    ) -> dict[str | tuple[str, str], _TrackDeltaItem]:
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem] = {}
        for b in blobs:
            try:
                content = b.download_as_bytes(timeout=self._timeout)
                table = pq.read_table(io.BytesIO(content))
                for row in table.to_pylist():
                    preview = row.get("itunes_preview_url") or row.get("preview_url")
                    genre = row.get("genre")
                    if not preview and not genre:
                        continue
                    sid = str(row.get("spotify_id") or "").strip()
                    title = str(row.get("title") or "").strip().lower()
                    artist = str(row.get("artist") or "").strip().lower()
                    item = _TrackDeltaItem(
                        preview_url=str(preview) if preview else None,
                        genre=str(genre) if genre else None,
                    )
                    if sid:
                        delta_map[sid] = item
                    if title and artist:
                        delta_map[(title, artist)] = item
            except (pa.ArrowInvalid, ValueError, KeyError, RuntimeError) as exc:
                logger.debug("Skipping unreadable delta blob %s: %s", b.name, exc)
                continue
        return delta_map

    def _apply_delta_to_track(
        self,
        track: CatalogSourceTrack,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    ) -> CatalogSourceTrack:
        title = (track.title or "").strip().lower()
        artist = (track.artist or "").strip().lower()
        delta = None
        if track.spotify_id and track.spotify_id in delta_map:
            delta = delta_map[track.spotify_id]
        elif (title, artist) in delta_map:
            delta = delta_map[(title, artist)]

        if delta is None:
            return track

        new_preview = delta.preview_url or track.itunes_preview_url
        new_genre = delta.genre or track.genre
        if new_preview == track.itunes_preview_url and new_genre == track.genre:
            return track

        return CatalogSourceTrack(
            title=track.title,
            artist=track.artist,
            duration_seconds=track.duration_seconds,
            genre=new_genre,
            album=track.album,
            country=track.country,
            release_year=track.release_year,
            cover_url=track.cover_url,
            spotify_id=track.spotify_id,
            itunes_preview_url=new_preview,
            explicit=track.explicit,
        )

    def parse_parquet_bytes(self, content_bytes: bytes) -> Sequence[CatalogSourceTrack]:
        """Parses in-memory Parquet file bytes into CatalogSourceTrack objects."""
        try:
            buffer = io.BytesIO(content_bytes)
            table = pq.read_table(buffer)
            records: list[dict[str, Any]] = table.to_pylist()
        except Exception as exc:
            logger.error(  # noqa: TRY400
                "Failed to parse Parquet content from '%s': %s",
                self._file_path,
                exc,
            )
            raise ExternalServiceError(
                "Failed to parse Parquet content from catalog file.",
                service_name="GCP_GCS",
            ) from exc

        tracks: list[CatalogSourceTrack] = []
        for record in records:
            raw_title = record.get("title")
            raw_artist = record.get("artist")
            if not raw_title or not raw_artist:
                continue

            raw_duration = record.get("duration_seconds")
            duration_seconds = 180
            if raw_duration is not None:
                with contextlib.suppress(ValueError, TypeError):
                    parsed_duration = int(raw_duration)
                    if parsed_duration > 0:
                        duration_seconds = parsed_duration

            raw_year = record.get("release_year")
            release_year: int | None = None
            if raw_year is not None:
                with contextlib.suppress(ValueError, TypeError):
                    release_year = int(raw_year)

            track = CatalogSourceTrack(
                title=str(raw_title).strip(),
                artist=str(raw_artist).strip(),
                duration_seconds=duration_seconds,
                genre=str(record.get("genre") or "Unknown").strip(),
                album=str(record["album"]).strip() if record.get("album") else None,
                country=str(record["country"]).strip()
                if record.get("country")
                else None,
                release_year=release_year,
                cover_url=str(record["cover_url"]).strip()
                if record.get("cover_url")
                else None,
                spotify_id=str(record["spotify_id"]).strip()
                if record.get("spotify_id")
                else None,
                itunes_preview_url=str(record["itunes_preview_url"]).strip()
                if record.get("itunes_preview_url")
                else None,
                explicit=bool(record.get("explicit", False)),
            )
            tracks.append(track)

        return tracks


__all__ = ["GCSTrackCatalogAdapter"]
