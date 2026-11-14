"""Adapter for fetching and compacting catalog tracks from a GCP Cloud Storage Parquet file."""

import contextlib
import io
import json
import logging
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
lazy from collections.abc import Iterator, Sequence

import pyarrow as pa
import pyarrow.parquet as pq
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage

from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    CatalogVersionInfo,
    TrackCatalogFilePort,
)
from app.domain.exceptions import ExternalServiceError

logger = logging.getLogger("app.infrastructure.gcs_track_catalog")


_DELTA_PARQUET_SCHEMA = pa.schema(
    [
        pa.field("spotify_id", pa.string()),
        pa.field("title", pa.string()),
        pa.field("artist", pa.string()),
        pa.field("album", pa.string()),
        pa.field("duration_seconds", pa.int64()),
        pa.field("genre", pa.string()),
        pa.field("country", pa.string()),
        pa.field("release_year", pa.int64()),
        pa.field("cover_url", pa.string()),
        pa.field("itunes_preview_url", pa.string()),
        pa.field("explicit", pa.int64()),
        pa.field("is_deleted", pa.int64()),
        pa.field("created_at", pa.string()),
    ]
)


@dataclass(slots=True, frozen=True)
class _TrackDeltaItem:
    spotify_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    duration_seconds: int | None = None
    genre: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    preview_url: str | None = None
    explicit: bool | None = None
    is_deleted: bool | None = None
    created_at: str | None = None
    seq: int = 0


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
        delta_map = self._load_pending_deltas(bucket)
        if not delta_map:
            return base_tracks

        merged = [self._apply_delta_to_track(t, delta_map) for t in base_tracks]
        existing_sids = {
            str(t.spotify_id).strip() for t in merged if str(t.spotify_id or "").strip()
        }
        existing_keys = {
            ((t.title or "").strip().lower(), (t.artist or "").strip().lower())
            for t in merged
            if (t.title or "").strip() and (t.artist or "").strip()
        }
        merged.extend(
            CatalogSourceTrack(
                title=delta.title or "",
                artist=delta.artist or "Unknown Artist",
                duration_seconds=delta.duration_seconds or 180,
                genre=delta.genre or "Unknown",
                album=delta.album,
                country=delta.country,
                release_year=delta.release_year,
                cover_url=delta.cover_url,
                spotify_id=delta.spotify_id,
                itunes_preview_url=delta.preview_url,
                explicit=bool(delta.explicit) if delta.explicit is not None else False,
            )
            for delta in self._iter_new_deltas(delta_map, existing_sids, existing_keys)
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
            delta_map = self._load_pending_deltas(bucket)
            existing_sids: set[str] = set()
            existing_keys: set[tuple[str, str]] = set()
            pf = pq.ParquetFile(tmp_path)
            for batch in pf.iter_batches(batch_size=batch_size):
                parsed = self._parse_records(batch.to_pylist())
                if delta_map:
                    parsed = [self._apply_delta_to_track(t, delta_map) for t in parsed]
                    for t in parsed:
                        if t.spotify_id:
                            existing_sids.add(t.spotify_id.strip())
                        if t.title and t.artist:
                            existing_keys.add(
                                (t.title.strip().lower(), t.artist.strip().lower())
                            )
                if parsed:
                    yield parsed

            if delta_map:
                new_tracks = [
                    CatalogSourceTrack(
                        title=delta.title or "",
                        artist=delta.artist or "Unknown Artist",
                        duration_seconds=delta.duration_seconds or 180,
                        genre=delta.genre or "Unknown",
                        album=delta.album,
                        country=delta.country,
                        release_year=delta.release_year,
                        cover_url=delta.cover_url,
                        spotify_id=delta.spotify_id,
                        itunes_preview_url=delta.preview_url,
                        explicit=bool(delta.explicit)
                        if delta.explicit is not None
                        else False,
                    )
                    for delta in self._iter_new_deltas(
                        delta_map, existing_sids, existing_keys
                    )
                ]
                if new_tracks:
                    yield new_tracks
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

            now_iso = created_at or datetime.now(UTC).isoformat()
            data: dict[str, list[Any]] = {
                "spotify_id": [spotify_id],
                "title": [title],
                "artist": [artist],
                "album": [album],
                "duration_seconds": [
                    int(duration_seconds) if duration_seconds is not None else 180
                ],
                "genre": [genre or "Unknown"],
                "country": [country],
                "release_year": [
                    int(release_year) if release_year is not None else None
                ],
                "cover_url": [cover_url],
                "itunes_preview_url": [preview_url],
                "explicit": [int(bool(explicit)) if explicit is not None else 0],
                "is_deleted": [int(bool(is_deleted)) if is_deleted is not None else 0],
                "created_at": [now_iso],
            }
            table = pa.Table.from_pydict(data, schema=_DELTA_PARQUET_SCHEMA)
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
            logger.exception(
                "Failed to write track delta to GCS bucket '%s'",
                self._bucket_name,
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
        existing_sids: set[str] = set()
        existing_keys: set[tuple[str, str]] = set()
        for record in records:
            spotify_id = str(record.get("spotify_id") or "").strip()
            title = str(record.get("title") or "").strip().lower()
            artist = str(record.get("artist") or "").strip().lower()
            if spotify_id:
                existing_sids.add(spotify_id)
            if title and artist:
                existing_keys.add((title, artist))
            delta = self._lookup_track_delta(delta_map, spotify_id, title, artist)
            if delta is not None:
                if delta.preview_url:
                    record["itunes_preview_url"] = delta.preview_url
                if delta.genre:
                    record["genre"] = delta.genre
                if delta.cover_url:
                    record["cover_url"] = delta.cover_url
            updated_records.append(record)
        for delta in self._iter_new_deltas(delta_map, existing_sids, existing_keys):
            new_rec: dict[str, Any] = {
                "spotify_id": delta.spotify_id,
                "title": delta.title or "",
                "artist": delta.artist or "Unknown Artist",
                "album": delta.album,
                "duration_seconds": delta.duration_seconds or 180,
                "genre": delta.genre or "Unknown",
                "country": delta.country,
                "release_year": delta.release_year,
                "cover_url": delta.cover_url,
                "itunes_preview_url": delta.preview_url,
                "explicit": int(bool(delta.explicit))
                if delta.explicit is not None
                else 0,
            }
            updated_records.append(new_rec)
        return updated_records

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

            table = pq.read_table(io.BytesIO(base_bytes))
            records = table.to_pylist()
            updated_records = self._apply_deltas_to_records(records, delta_map)

            schema = self._resolve_compaction_schema(table.schema, updated_records)
            updated_table = pa.Table.from_pylist(updated_records, schema=schema)
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
        except (GoogleAPIError, OSError) as exc:
            logger.warning("Failed to load pending catalog deltas: %s", exc)
            return {}

    @staticmethod
    def _resolve_compaction_schema(
        base_schema: pa.Schema,
        records: Sequence[dict[str, Any]],
    ) -> pa.Schema:
        schema = base_schema
        for col in ("itunes_preview_url", "genre", "cover_url"):
            if not any(r.get(col) is not None for r in records):
                continue
            if col not in schema.names:
                schema = schema.append(pa.field(col, pa.string()))
            else:
                idx = schema.get_field_index(col)
                if pa.types.is_null(schema.field(idx).type):
                    schema = schema.set(idx, pa.field(col, pa.string()))
        return schema

    @staticmethod
    def _merge_delta_items(
        older: _TrackDeltaItem | None,
        newer: _TrackDeltaItem | None,
    ) -> _TrackDeltaItem | None:
        if older is None:
            return newer
        if newer is None:
            return older
        first, second = (older, newer) if newer.seq >= older.seq else (newer, older)
        return _TrackDeltaItem(
            spotify_id=second.spotify_id or first.spotify_id,
            title=second.title or first.title,
            artist=second.artist or first.artist,
            album=second.album or first.album,
            duration_seconds=second.duration_seconds
            if second.duration_seconds is not None
            else first.duration_seconds,
            genre=second.genre or first.genre,
            country=second.country or first.country,
            release_year=second.release_year
            if second.release_year is not None
            else first.release_year,
            cover_url=second.cover_url or first.cover_url,
            preview_url=second.preview_url or first.preview_url,
            explicit=second.explicit if second.explicit is not None else first.explicit,
            is_deleted=second.is_deleted
            if second.is_deleted is not None
            else first.is_deleted,
            created_at=second.created_at or first.created_at,
            seq=max(first.seq, second.seq),
        )

    @staticmethod
    def _iter_new_deltas(
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
        existing_sids: set[str],
        existing_keys: set[tuple[str, str]],
    ) -> list[_TrackDeltaItem]:
        new_items: list[_TrackDeltaItem] = []
        seen_ids: set[int] = set()
        for delta in delta_map.values():
            if id(delta) in seen_ids or delta.is_deleted:
                continue
            seen_ids.add(id(delta))
            sid = str(delta.spotify_id or "").strip()
            t_norm = (delta.title or "").strip().lower()
            a_norm = (delta.artist or "").strip().lower()
            if (sid and sid in existing_sids) or (
                t_norm and a_norm and (t_norm, a_norm) in existing_keys
            ):
                continue
            if not t_norm or not a_norm:
                continue
            if sid:
                existing_sids.add(sid)
            existing_keys.add((t_norm, a_norm))
            new_items.append(delta)
        return new_items

    @classmethod
    def _lookup_track_delta(
        cls,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
        spotify_id: str,
        title: str,
        artist: str,
    ) -> _TrackDeltaItem | None:
        by_sid = delta_map.get(spotify_id) if spotify_id else None
        by_title = delta_map.get((title, artist)) if title and artist else None
        return cls._merge_delta_items(by_title, by_sid)

    def _read_deltas_from_blobs(
        self, blobs: Sequence[storage.Blob]
    ) -> dict[str | tuple[str, str], _TrackDeltaItem]:
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem] = {}
        seq = 0
        for b in blobs:
            try:
                content = b.download_as_bytes(timeout=self._timeout)
                table = pq.read_table(io.BytesIO(content))
                for row in table.to_pylist():
                    seq += 1
                    preview = row.get("itunes_preview_url") or row.get("preview_url")
                    genre = row.get("genre")
                    cover_url = row.get("cover_url")
                    sid = str(row.get("spotify_id") or "").strip()
                    raw_title = str(row.get("title") or "").strip()
                    raw_artist = str(row.get("artist") or "").strip()
                    title = raw_title.lower()
                    artist = raw_artist.lower()
                    existing = self._lookup_track_delta(delta_map, sid, title, artist)
                    raw_dur = row.get("duration_seconds")
                    raw_year = row.get("release_year")
                    incoming = _TrackDeltaItem(
                        spotify_id=sid or None,
                        title=raw_title or None,
                        artist=raw_artist or None,
                        album=str(row["album"]) if row.get("album") else None,
                        duration_seconds=int(raw_dur) if raw_dur is not None else None,
                        genre=str(genre) if genre else None,
                        country=str(row["country"]) if row.get("country") else None,
                        release_year=int(raw_year) if raw_year is not None else None,
                        cover_url=str(cover_url) if cover_url else None,
                        preview_url=str(preview) if preview else None,
                        explicit=bool(row["explicit"])
                        if row.get("explicit") is not None
                        else None,
                        is_deleted=bool(row["is_deleted"])
                        if row.get("is_deleted") is not None
                        else None,
                        created_at=str(row["created_at"])
                        if row.get("created_at")
                        else None,
                        seq=seq,
                    )
                    merged = self._merge_delta_items(existing, incoming)
                    if merged is None:
                        continue
                    if sid:
                        delta_map[sid] = merged
                    if title and artist:
                        delta_map[(title, artist)] = merged
            except (pa.ArrowInvalid, ValueError, KeyError) as exc:
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
        delta = self._lookup_track_delta(
            delta_map, str(track.spotify_id or "").strip(), title, artist
        )

        if delta is None:
            return track

        new_preview = delta.preview_url or track.itunes_preview_url
        new_genre = delta.genre or track.genre
        new_cover = delta.cover_url or track.cover_url
        if (
            new_preview == track.itunes_preview_url
            and new_genre == track.genre
            and new_cover == track.cover_url
        ):
            return track

        return CatalogSourceTrack(
            title=track.title,
            artist=track.artist,
            duration_seconds=track.duration_seconds,
            genre=new_genre,
            album=track.album,
            country=track.country,
            release_year=track.release_year,
            cover_url=new_cover,
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
            logger.exception(
                "Failed to parse Parquet content from '%s'",
                self._file_path,
            )
            raise ExternalServiceError(
                "Failed to parse Parquet content from catalog file.",
                service_name="GCP_GCS",
            ) from exc

        return self._parse_records(records)

    @staticmethod
    def _parse_records(records: Sequence[dict[str, Any]]) -> list[CatalogSourceTrack]:
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
