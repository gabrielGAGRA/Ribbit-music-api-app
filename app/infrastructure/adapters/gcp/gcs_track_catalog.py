"""Adapter for fetching and compacting catalog tracks from a GCP Cloud Storage Parquet file."""

import contextlib
import io
import json
import logging
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
lazy from collections.abc import Iterator, Sequence

import pyarrow as pa
import pyarrow.compute as _pc
import pyarrow.parquet as pq
import urllib3
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage
from requests.adapters import HTTPAdapter

from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    CatalogVersionInfo,
    TrackCatalogFilePort,
)
from app.domain.exceptions import ExternalServiceError

logger = logging.getLogger("app.infrastructure.gcs_track_catalog")
pc: Any = _pc

_COMPACT_BATCH_SIZE = 100_000
_MIN_DT = datetime.min.replace(tzinfo=UTC)

_DELTA_PARQUET_SCHEMA = pa.schema(
    [
        pa.field("spotify_id", pa.string()),
        pa.field("title", pa.string()),
        pa.field("artist", pa.string()),
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


def _parse_iso_dt(raw: object) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    with contextlib.suppress(ValueError):
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return None


def _blob_sort_dt(blob: Any, row_created_at: object) -> datetime:
    parsed = _parse_iso_dt(row_created_at)
    if parsed is not None:
        return parsed
    tc = getattr(blob, "time_created", None)
    if isinstance(tc, datetime):
        return tc if tc.tzinfo is not None else tc.replace(tzinfo=UTC)
    return _MIN_DT


def _is_known_genre(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip().lower() != "unknown")


def _is_truthy_flag(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "t", "y"}


def _coerce_flag_for_arrow(value: bool, field_type: pa.DataType) -> object:
    if pa.types.is_string(field_type) or pa.types.is_large_string(field_type):
        return "1" if value else "0"
    if pa.types.is_boolean(field_type):
        return value
    return int(value)


def _prefer_genre(older: str | None, newer: str | None) -> str | None:
    if _is_known_genre(newer):
        return newer
    if _is_known_genre(older):
        return older
    return newer or older


class _GCSHTTPAdapter(HTTPAdapter):
    """Requests HTTPAdapter forcing HTTP/1.1 to avoid urllib3 HTTP/3 QUIC upload stalls."""

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> None:
        http_version = getattr(urllib3, "HttpVersion", None)
        if http_version is not None:
            pool_kwargs["disabled_svn"] = {http_version.h2, http_version.h3}
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


class GCSTrackCatalogAdapter(TrackCatalogFilePort):
    """GCP Cloud Storage adapter reading and updating music catalog tracks."""

    def __init__(
        self,
        *,
        bucket_name: str,
        file_path: str = "Songs/tracks.parquet",
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
            client = storage.Client()
            http_session = getattr(client, "_http", None)
            if http_session is not None and hasattr(http_session, "mount"):
                http_session.mount(
                    "https://",
                    _GCSHTTPAdapter(pool_connections=16, pool_maxsize=16),
                )
            self._storage_client = client
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

        matched_delta_ids: set[int] = set()
        merged: list[CatalogSourceTrack] = []
        for track in base_tracks:
            updated = self._apply_delta_to_track(track, delta_map, matched_delta_ids)
            if updated is not None:
                merged.append(updated)
        merged.extend(
            self._delta_to_catalog_track(delta)
            for delta in self._iter_new_deltas(delta_map, matched_delta_ids)
        )
        return merged

    @staticmethod
    def _delta_to_catalog_track(delta: _TrackDeltaItem) -> CatalogSourceTrack:
        return CatalogSourceTrack(
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
            explicit=delta.explicit if delta.explicit is not None else False,
        )

    def _download_catalog_to_temp(self, bucket: storage.Bucket) -> Path:
        tmp_path: Path | None = None
        try:
            blob = bucket.blob(self._file_path)
            with tempfile.NamedTemporaryFile(
                suffix=".parquet", delete=False
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
            if isinstance(blob, storage.Blob) or not hasattr(blob, "download_as_bytes"):
                blob.download_to_filename(
                    str(tmp_path), timeout=max(self._timeout, 300.0)
                )
            else:
                # Unit-test mocks may only stub download_to_filename or download_as_bytes.
                try:
                    blob.download_to_filename(
                        str(tmp_path), timeout=max(self._timeout, 300.0)
                    )
                    if tmp_path.stat().st_size == 0:
                        tmp_path.write_bytes(
                            blob.download_as_bytes(timeout=self._timeout)
                        )
                except AttributeError:
                    tmp_path.write_bytes(blob.download_as_bytes(timeout=self._timeout))
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

    def _download_blob_to_temp(self, blob: Any) -> Path:
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".parquet", delete=False
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
            if isinstance(blob, storage.Blob):
                blob.download_to_filename(
                    str(tmp_path), timeout=max(self._timeout, 300.0)
                )
            else:
                tmp_path.write_bytes(blob.download_as_bytes(timeout=self._timeout))
        except Exception:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
            raise
        else:
            return tmp_path

    def _iter_parquet_batches(
        self,
        tmp_path: Path,
        batch_size: int,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
        matched_delta_ids: set[int],
    ) -> Iterator[list[CatalogSourceTrack]]:
        limit = self._max_tracks if self._max_tracks and self._max_tracks > 0 else None
        effective_batch = min(batch_size, limit) if limit is not None else batch_size
        yielded = 0
        with pq.ParquetFile(tmp_path) as pf:
            for batch in pf.iter_batches(batch_size=effective_batch):
                parsed = self._parse_records(batch.to_pylist())
                if limit is not None:
                    parsed = parsed[: max(limit - yielded, 0)]
                if delta_map and parsed:
                    parsed = [
                        updated
                        for t in parsed
                        if (
                            updated := self._apply_delta_to_track(
                                t, delta_map, matched_delta_ids
                            )
                        )
                        is not None
                    ]
                if parsed:
                    yielded += len(parsed)
                    yield parsed
                if limit is not None and yielded >= limit:
                    break

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
            matched_delta_ids: set[int] = set()
            yield from self._iter_parquet_batches(
                tmp_path, batch_size, delta_map, matched_delta_ids
            )
            if delta_map:
                new_tracks = [
                    self._delta_to_catalog_track(delta)
                    for delta in self._iter_new_deltas(delta_map, matched_delta_ids)
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

            now_dt = datetime.now(UTC)
            now_iso = created_at or now_dt.isoformat()
            data: dict[str, list[Any]] = {
                "spotify_id": [spotify_id],
                "title": [title],
                "artist": [artist],
                "duration_seconds": [duration_seconds],
                "genre": [genre],
                "country": [country],
                "release_year": [release_year],
                "cover_url": [cover_url],
                "itunes_preview_url": [preview_url],
                "explicit": [int(explicit) if explicit is not None else None],
                "is_deleted": [int(is_deleted) if is_deleted is not None else None],
                "created_at": [now_iso],
            }
            table = pa.Table.from_pydict(data, schema=_DELTA_PARQUET_SCHEMA)
            sink = io.BytesIO()
            pq.write_table(table, sink)
            parquet_bytes = sink.getvalue()

            ts_tag = now_dt.strftime("%Y%m%dT%H%M%S%f")
            delta_blob_name = (
                f"{self._delta_prefix}/delta_{ts_tag}_{uuid.uuid4().hex[:8]}.parquet"
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

    @staticmethod
    def _apply_delta_to_record(
        record: dict[str, Any],
        delta: _TrackDeltaItem,
        schema: pa.Schema,
    ) -> None:
        schema_names = set(schema.names)
        if (
            delta.spotify_id
            and not record.get("spotify_id")
            and "spotify_id" in schema_names
        ):
            record["spotify_id"] = delta.spotify_id
        if "genre" in schema_names:
            merged_genre = _prefer_genre(
                str(record["genre"]) if record.get("genre") else None,
                delta.genre,
            )
            if merged_genre is not None:
                record["genre"] = merged_genre
        explicit_val = (
            _coerce_flag_for_arrow(delta.explicit, schema.field("explicit").type)
            if delta.explicit is not None and "explicit" in schema_names
            else None
        )
        is_deleted_val = (
            _coerce_flag_for_arrow(delta.is_deleted, schema.field("is_deleted").type)
            if delta.is_deleted is not None and "is_deleted" in schema_names
            else None
        )
        updates: tuple[tuple[str, Any], ...] = (
            ("itunes_preview_url", delta.preview_url),
            ("cover_url", delta.cover_url),
            ("country", delta.country),
            ("album", delta.album),
            ("release_year", delta.release_year),
            ("explicit", explicit_val),
            ("is_deleted", is_deleted_val),
        )
        record.update(
            {
                col: val
                for col, val in updates
                if val is not None and col in schema_names
            }
        )

    @staticmethod
    def _build_new_compaction_record(
        delta: _TrackDeltaItem,
        schema: pa.Schema,
        next_track_id: int,
        now_iso: str,
    ) -> dict[str, Any]:
        schema_names = set(schema.names)
        explicit_val = (
            _coerce_flag_for_arrow(
                delta.explicit if delta.explicit is not None else False,
                schema.field("explicit").type,
            )
            if "explicit" in schema_names
            else 0
        )
        is_deleted_val = (
            _coerce_flag_for_arrow(False, schema.field("is_deleted").type)
            if "is_deleted" in schema_names
            else 0
        )
        full: dict[str, Any] = {
            "track_id": next_track_id,
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
            "explicit": explicit_val,
            "is_deleted": is_deleted_val,
            "created_at": delta.created_at or now_iso,
        }
        return {col: full.get(col) for col in schema_names}

    @staticmethod
    def _extract_delta_lookup_sets(
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    ) -> tuple[set[str], set[str]]:
        delta_sids: set[str] = set()
        delta_titles: set[str] = set()
        for key in delta_map:
            if isinstance(key, str):
                delta_sids.add(key)
            else:
                delta_titles.add(key[0])
        return delta_sids, delta_titles

    @staticmethod
    def _batch_has_delta_match(
        batch: pa.RecordBatch,
        delta_sids: set[str],
        delta_titles: set[str],
    ) -> bool:
        names = set(batch.schema.names)
        if delta_sids and "spotify_id" in names:
            col = batch.column("spotify_id")
            if pa.types.is_string(col.type) or pa.types.is_large_string(col.type):
                trimmed = pc.utf8_trim_whitespace(col)
                sid_set = pa.array(list(delta_sids), type=col.type)
                if pc.any(pc.is_in(trimmed, value_set=sid_set)).as_py():
                    return True
        if delta_titles and "title" in names:
            col = batch.column("title")
            if pa.types.is_string(col.type) or pa.types.is_large_string(col.type):
                lowered = pc.utf8_lower(pc.utf8_trim_whitespace(col))
                title_set = pa.array(list(delta_titles), type=col.type)
                if pc.any(pc.is_in(lowered, value_set=title_set)).as_py():
                    return True
        return False

    @staticmethod
    def _align_batch_to_schema(
        batch: pa.RecordBatch, target_schema: pa.Schema
    ) -> pa.RecordBatch:
        if batch.schema.equals(target_schema):
            return batch
        batch_names = set(batch.schema.names)
        arrays: list[pa.Array[Any]] = []
        for field in target_schema:
            if field.name in batch_names:
                col = batch.column(field.name)
                arrays.append(
                    col if col.type.equals(field.type) else col.cast(field.type)
                )
            else:
                arrays.append(pa.nulls(batch.num_rows, type=field.type))
        return pa.RecordBatch.from_arrays(arrays, schema=target_schema)

    def _compact_parquet_files(
        self,
        src_path: Path,
        dst_path: Path,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    ) -> None:
        with pq.ParquetFile(src_path) as pf:
            schema = self._resolve_compaction_schema(pf.schema_arrow, delta_map)
            schema_names = set(schema.names)
            has_track_id = "track_id" in schema_names
            delta_sids, delta_titles = self._extract_delta_lookup_sets(delta_map)
            matched_delta_ids: set[int] = set()
            max_track_id = 0

            with pq.ParquetWriter(dst_path, schema, compression="zstd") as writer:
                for batch in pf.iter_batches(batch_size=_COMPACT_BATCH_SIZE):
                    if has_track_id and batch.num_rows > 0:
                        batch_max = pc.max(batch.column("track_id")).as_py()
                        if isinstance(batch_max, int) and batch_max > max_track_id:
                            max_track_id = batch_max

                    if not self._batch_has_delta_match(batch, delta_sids, delta_titles):
                        writer.write_batch(self._align_batch_to_schema(batch, schema))
                        continue

                    records = batch.to_pylist()
                    for record in records:
                        sid = str(record.get("spotify_id") or "").strip()
                        title = str(record.get("title") or "").strip().lower()
                        artist = str(record.get("artist") or "").strip().lower()
                        delta = self._lookup_track_delta(
                            delta_map, sid, title, artist, matched_delta_ids
                        )
                        if delta is not None:
                            self._apply_delta_to_record(record, delta, schema)
                    writer.write_table(pa.Table.from_pylist(records, schema=schema))

                new_deltas = self._iter_new_deltas(delta_map, matched_delta_ids)
                if new_deltas:
                    now_iso = datetime.now(UTC).isoformat()
                    new_records = [
                        self._build_new_compaction_record(
                            delta, schema, max_track_id + idx, now_iso
                        )
                        for idx, delta in enumerate(new_deltas, start=1)
                    ]
                    writer.write_table(pa.Table.from_pylist(new_records, schema=schema))

    def _delete_delta_blobs(self, blobs: Sequence[storage.Blob]) -> None:
        def _delete_one(blob: storage.Blob) -> None:
            try:
                blob.delete(timeout=self._timeout)
            except (GoogleAPIError, RuntimeError, OSError) as exc:
                logger.warning(
                    "Failed to delete processed delta blob '%s' from GCS bucket '%s': %s",
                    blob.name,
                    self._bucket_name,
                    exc,
                )

        if len(blobs) <= 1:
            for blob in blobs:
                _delete_one(blob)
            return
        with ThreadPoolExecutor(max_workers=min(16, len(blobs))) as executor:
            list(executor.map(_delete_one, blobs))

    def compact_catalog(self) -> int:
        """Consolidates pending deltas into base catalog file, cleanses deltas, bumps version."""
        if not self._bucket_name:
            raise ExternalServiceError(
                "GCS bucket name is not configured.", service_name="GCP_GCS"
            )

        t0 = time.perf_counter()
        client = self._get_client()
        src_tmp: Path | None = None
        dst_tmp: Path | None = None
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
            logger.info(
                "Compaction loaded %d deltas (%d keys) from bucket '%s' in %.2fs",
                len(delta_blobs),
                len(delta_map),
                self._bucket_name,
                time.perf_counter() - t0,
            )

            base_blob = bucket.blob(self._file_path)
            src_tmp = self._download_blob_to_temp(base_blob)
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as out_f:
                dst_tmp = Path(out_f.name)

            self._compact_parquet_files(src_tmp, dst_tmp, delta_map)
            logger.info(
                "Compaction merged base Parquet (%d -> %d bytes) in %.2fs",
                src_tmp.stat().st_size,
                dst_tmp.stat().st_size,
                time.perf_counter() - t0,
            )

            if isinstance(base_blob, storage.Blob):
                base_blob.upload_from_filename(
                    str(dst_tmp),
                    content_type="application/octet-stream",
                    timeout=max(self._timeout, 600.0),
                )
            else:
                base_blob.upload_from_string(
                    dst_tmp.read_bytes(),
                    content_type="application/octet-stream",
                    timeout=self._timeout,
                )
            logger.info(
                "Compaction uploaded base Parquet to '%s' in %.2fs",
                self._file_path,
                time.perf_counter() - t0,
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
            logger.info(
                "Compaction published v%d and cleaned up %d deltas in %.2fs",
                new_version,
                len(delta_blobs),
                time.perf_counter() - t0,
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
        finally:
            for path in (src_tmp, dst_tmp):
                if path is not None:
                    with contextlib.suppress(OSError):
                        path.unlink(missing_ok=True)

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
            return self._read_deltas_from_blobs(delta_blobs, ignore_blob_errors=True)
        except (GoogleAPIError, OSError) as exc:
            logger.warning("Failed to load pending catalog deltas: %s", exc)
            return {}

    @staticmethod
    def _resolve_compaction_schema(
        base_schema: pa.Schema,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    ) -> pa.Schema:
        schema = base_schema
        deltas = list(delta_map.values())
        present = {
            "itunes_preview_url": any(d.preview_url is not None for d in deltas),
            "genre": any(d.genre is not None for d in deltas),
            "cover_url": any(d.cover_url is not None for d in deltas),
            "country": any(d.country is not None for d in deltas),
        }
        for col, has_val in present.items():
            if not has_val:
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
            genre=_prefer_genre(first.genre, second.genre),
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
        matched_delta_ids: set[int],
    ) -> list[_TrackDeltaItem]:
        new_items: list[_TrackDeltaItem] = []
        seen_ids: set[int] = set(matched_delta_ids)
        seen_sids: set[str] = set()
        seen_keys: set[tuple[str, str]] = set()
        for delta in delta_map.values():
            if id(delta) in seen_ids or delta.is_deleted:
                continue
            seen_ids.add(id(delta))
            sid = (delta.spotify_id or "").strip()
            t_norm = (delta.title or "").strip().lower()
            a_norm = (delta.artist or "").strip().lower()
            if (sid and sid in seen_sids) or (
                t_norm and a_norm and (t_norm, a_norm) in seen_keys
            ):
                continue
            if not t_norm or not a_norm:
                continue
            if delta.duration_seconds is None or delta.explicit is None:
                continue
            if sid:
                seen_sids.add(sid)
            seen_keys.add((t_norm, a_norm))
            new_items.append(delta)
        return new_items

    @classmethod
    def _lookup_track_delta(
        cls,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
        spotify_id: str,
        title: str,
        artist: str,
        matched_delta_ids: set[int] | None = None,
    ) -> _TrackDeltaItem | None:
        by_sid = delta_map.get(spotify_id) if spotify_id else None
        by_title = delta_map.get((title, artist)) if title and artist else None
        if matched_delta_ids is not None:
            if by_sid is not None:
                matched_delta_ids.add(id(by_sid))
            if by_title is not None:
                matched_delta_ids.add(id(by_title))
        return cls._merge_delta_items(by_title, by_sid)

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

    @staticmethod
    def _row_to_delta_item(row: dict[str, Any], seq: int) -> _TrackDeltaItem:
        preview = row.get("itunes_preview_url") or row.get("preview_url")
        genre = row.get("genre")
        cover_url = row.get("cover_url")
        sid = str(row.get("spotify_id") or "").strip()
        raw_title = str(row.get("title") or "").strip()
        raw_artist = str(row.get("artist") or "").strip()
        raw_dur = row.get("duration_seconds")
        raw_year = row.get("release_year")
        return _TrackDeltaItem(
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
            explicit=_is_truthy_flag(row["explicit"])
            if row.get("explicit") is not None
            else None,
            is_deleted=_is_truthy_flag(row["is_deleted"])
            if row.get("is_deleted") is not None
            else None,
            created_at=str(row["created_at"]) if row.get("created_at") else None,
            seq=seq,
        )

    def _read_deltas_from_blobs(
        self, blobs: Sequence[storage.Blob], *, ignore_blob_errors: bool = False
    ) -> dict[str | tuple[str, str], _TrackDeltaItem]:
        staged: list[tuple[datetime, int, dict[str, Any]]] = []
        raw_idx = 0
        for b, content in zip(
            blobs,
            self._download_delta_bytes_batch(
                blobs, ignore_blob_errors=ignore_blob_errors
            ),
            strict=True,
        ):
            if content is None:
                continue
            try:
                table = pq.read_table(io.BytesIO(content))
                for row in table.to_pylist():
                    raw_idx += 1
                    staged.append(
                        (_blob_sort_dt(b, row.get("created_at")), raw_idx, row)
                    )
            except (pa.ArrowInvalid, ValueError, KeyError) as exc:
                logger.debug("Skipping unreadable delta blob %s: %s", b.name, exc)
                continue

        staged.sort(key=lambda item: (item[0], item[1]))
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem] = {}
        for seq, (_, _, row) in enumerate(staged, start=1):
            incoming = self._row_to_delta_item(row, seq)
            sid = incoming.spotify_id or ""
            title = (incoming.title or "").lower()
            artist = (incoming.artist or "").lower()
            existing = self._lookup_track_delta(delta_map, sid, title, artist)
            merged = self._merge_delta_items(existing, incoming)
            if merged is None:
                continue
            if sid:
                delta_map[sid] = merged
            if title and artist:
                delta_map[(title, artist)] = merged
        return delta_map

    def _apply_delta_to_track(
        self,
        track: CatalogSourceTrack,
        delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
        matched_delta_ids: set[int] | None = None,
    ) -> CatalogSourceTrack | None:
        title = (track.title or "").strip().lower()
        artist = (track.artist or "").strip().lower()
        delta = self._lookup_track_delta(
            delta_map,
            (track.spotify_id or "").strip(),
            title,
            artist,
            matched_delta_ids,
        )

        if delta is None:
            return track
        if delta.is_deleted:
            return None

        return CatalogSourceTrack(
            title=track.title,
            artist=track.artist,
            duration_seconds=track.duration_seconds,
            genre=_prefer_genre(track.genre, delta.genre) or "Unknown",
            album=delta.album or track.album,
            country=delta.country or track.country,
            release_year=delta.release_year
            if delta.release_year is not None
            else track.release_year,
            cover_url=delta.cover_url or track.cover_url,
            spotify_id=delta.spotify_id or track.spotify_id,
            itunes_preview_url=delta.preview_url or track.itunes_preview_url,
            explicit=delta.explicit if delta.explicit is not None else track.explicit,
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
            if _is_truthy_flag(record.get("is_deleted")):
                continue
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
                explicit=_is_truthy_flag(record.get("explicit", False)),
            )
            tracks.append(track)

        return tracks


__all__ = ["GCSTrackCatalogAdapter"]
