"""Parquet serialization, parsing, and delta-merge helpers for track catalog files."""

import contextlib
import io
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.application.ports.services.catalog_source import CatalogSourceTrack
from app.domain.exceptions import ExternalServiceError

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

logger = logging.getLogger("app.infrastructure.gcs_track_catalog")

DELTA_PARQUET_SCHEMA = pa.schema(
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


def _optional_int(raw: Any) -> int | None:
    if raw is None:
        return None
    with contextlib.suppress(ValueError, TypeError):
        return int(raw)
    return None


def _optional_stripped_str(raw: Any) -> str | None:
    return str(raw).strip() if raw else None


def _parse_records(records: Sequence[dict[str, Any]]) -> list[CatalogSourceTrack]:
    tracks: list[CatalogSourceTrack] = []
    for record in records:
        raw_title = record.get("title")
        raw_artist = record.get("artist")
        if not raw_title or not raw_artist:
            continue

        parsed_duration = _optional_int(record.get("duration_seconds"))
        duration_seconds = (
            parsed_duration
            if parsed_duration is not None and parsed_duration > 0
            else 180
        )

        tracks.append(
            CatalogSourceTrack(
                title=str(raw_title).strip(),
                artist=str(raw_artist).strip(),
                duration_seconds=duration_seconds,
                genre=str(record.get("genre") or "Unknown").strip(),
                album=_optional_stripped_str(record.get("album")),
                country=_optional_stripped_str(record.get("country")),
                release_year=_optional_int(record.get("release_year")),
                cover_url=_optional_stripped_str(record.get("cover_url")),
                spotify_id=_optional_stripped_str(record.get("spotify_id")),
                itunes_preview_url=_optional_stripped_str(
                    record.get("itunes_preview_url")
                ),
                explicit=bool(record.get("explicit", False)),
            )
        )
    return tracks


def parse_parquet_bytes(
    content_bytes: bytes, *, file_path: str = "<bytes>"
) -> Sequence[CatalogSourceTrack]:
    """Parses in-memory Parquet file bytes into CatalogSourceTrack objects."""
    try:
        table = pq.read_table(io.BytesIO(content_bytes))
        records: list[dict[str, Any]] = table.to_pylist()
    except Exception as exc:
        logger.exception("Failed to parse Parquet content from '%s'", file_path)
        raise ExternalServiceError(
            "Failed to parse Parquet content from catalog file.",
            service_name="GCP_GCS",
        ) from exc

    return _parse_records(records)


def build_delta_parquet_bytes(
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
) -> bytes:
    """Serializes a single track delta record to Parquet bytes matching the catalog schema."""
    now_iso = created_at or datetime.now(UTC).isoformat()
    data: dict[str, list[Any]] = {
        "spotify_id": [spotify_id],
        "title": [title],
        "artist": [artist],
        "album": [album],
        "duration_seconds": [
            int(duration_seconds) if duration_seconds is not None else None
        ],
        "genre": [genre],
        "country": [country],
        "release_year": [int(release_year) if release_year is not None else None],
        "cover_url": [cover_url],
        "itunes_preview_url": [preview_url],
        "explicit": [int(bool(explicit)) if explicit is not None else None],
        "is_deleted": [int(bool(is_deleted)) if is_deleted is not None else None],
        "created_at": [now_iso],
    }
    table = pa.Table.from_pydict(data, schema=DELTA_PARQUET_SCHEMA)
    sink = io.BytesIO()
    pq.write_table(table, sink)
    return sink.getvalue()


def delta_to_catalog_track(delta: _TrackDeltaItem) -> CatalogSourceTrack:
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
        explicit=bool(delta.explicit) if delta.explicit is not None else False,
    )


def record_seen_keys(
    tracks: Sequence[CatalogSourceTrack],
    existing_sids: set[str],
    existing_keys: set[tuple[str, str]],
) -> None:
    for track in tracks:
        if track.spotify_id:
            existing_sids.add(track.spotify_id.strip())
        if track.title and track.artist:
            existing_keys.add(
                (track.title.strip().lower(), track.artist.strip().lower())
            )


def merge_delta_items(
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
        duration_seconds=(
            second.duration_seconds
            if second.duration_seconds is not None
            else first.duration_seconds
        ),
        genre=second.genre or first.genre,
        country=second.country or first.country,
        release_year=(
            second.release_year
            if second.release_year is not None
            else first.release_year
        ),
        cover_url=second.cover_url or first.cover_url,
        preview_url=second.preview_url or first.preview_url,
        explicit=second.explicit if second.explicit is not None else first.explicit,
        is_deleted=(
            second.is_deleted if second.is_deleted is not None else first.is_deleted
        ),
        created_at=second.created_at or first.created_at,
        seq=max(first.seq, second.seq),
    )


def lookup_track_delta(
    delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    spotify_id: str,
    title: str,
    artist: str,
) -> _TrackDeltaItem | None:
    by_sid = delta_map.get(spotify_id) if spotify_id else None
    by_title = delta_map.get((title, artist)) if title and artist else None
    return merge_delta_items(by_title, by_sid)


def iter_new_deltas(
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
        if delta.duration_seconds is None or delta.explicit is None:
            continue
        if sid:
            existing_sids.add(sid)
        existing_keys.add((t_norm, a_norm))
        new_items.append(delta)
    return new_items


def apply_delta_to_track(
    track: CatalogSourceTrack,
    delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
) -> CatalogSourceTrack:
    title = (track.title or "").strip().lower()
    artist = (track.artist or "").strip().lower()
    delta = lookup_track_delta(
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


def apply_deltas_to_records(
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
        delta = lookup_track_delta(delta_map, spotify_id, title, artist)
        if delta is not None:
            _apply_delta_fields_to_record(record, delta)
        updated_records.append(record)
    updated_records.extend(
        _delta_to_record(delta)
        for delta in iter_new_deltas(delta_map, existing_sids, existing_keys)
    )
    return updated_records


def _apply_delta_fields_to_record(
    record: dict[str, Any], delta: _TrackDeltaItem
) -> None:
    if delta.preview_url:
        record["itunes_preview_url"] = delta.preview_url
    if delta.genre:
        record["genre"] = delta.genre
    if delta.cover_url:
        record["cover_url"] = delta.cover_url


def _delta_to_record(delta: _TrackDeltaItem) -> dict[str, Any]:
    return {
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
        "explicit": int(bool(delta.explicit)) if delta.explicit is not None else 0,
    }


def _row_to_delta_item(
    row: dict[str, Any], seq: int
) -> tuple[str, str, str, _TrackDeltaItem]:
    preview = row.get("itunes_preview_url") or row.get("preview_url")
    genre = row.get("genre")
    cover_url = row.get("cover_url")
    sid = str(row.get("spotify_id") or "").strip()
    raw_title = str(row.get("title") or "").strip()
    raw_artist = str(row.get("artist") or "").strip()
    raw_dur = row.get("duration_seconds")
    raw_year = row.get("release_year")
    item = _TrackDeltaItem(
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
        explicit=bool(row["explicit"]) if row.get("explicit") is not None else None,
        is_deleted=(
            bool(row["is_deleted"]) if row.get("is_deleted") is not None else None
        ),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        seq=seq,
    )
    return sid, raw_title.lower(), raw_artist.lower(), item


def read_deltas_from_bytes(
    blob_contents: Sequence[tuple[str | None, bytes | None]],
) -> dict[str | tuple[str, str], _TrackDeltaItem]:
    """Parses downloaded delta Parquet blobs into a merged lookup map."""
    delta_map: dict[str | tuple[str, str], _TrackDeltaItem] = {}
    seq = 0
    for blob_name, content in blob_contents:
        if content is None:
            continue
        try:
            table = pq.read_table(io.BytesIO(content))
            for row in table.to_pylist():
                seq += 1
                sid, title, artist, incoming = _row_to_delta_item(row, seq)
                existing = lookup_track_delta(delta_map, sid, title, artist)
                merged = merge_delta_items(existing, incoming)
                if merged is None:
                    continue
                if sid:
                    delta_map[sid] = merged
                if title and artist:
                    delta_map[(title, artist)] = merged
        except (pa.ArrowInvalid, ValueError, KeyError) as exc:
            logger.debug("Skipping unreadable delta blob %s: %s", blob_name, exc)
            continue
    return delta_map


def resolve_compaction_schema(
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


def compact_parquet_bytes(
    base_bytes: bytes,
    delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
) -> bytes:
    """Applies pending deltas to base Parquet bytes and returns the compacted Parquet payload."""
    table = pq.read_table(io.BytesIO(base_bytes))
    updated_records = apply_deltas_to_records(table.to_pylist(), delta_map)
    schema = resolve_compaction_schema(table.schema, updated_records)
    updated_table = pa.Table.from_pylist(updated_records, schema=schema)
    sink = io.BytesIO()
    pq.write_table(updated_table, sink)
    return sink.getvalue()


def iter_parquet_file_batches(
    tmp_path: Path,
    batch_size: int,
    max_tracks: int | None,
    delta_map: dict[str | tuple[str, str], _TrackDeltaItem],
    existing_sids: set[str],
    existing_keys: set[tuple[str, str]],
) -> Iterator[list[CatalogSourceTrack]]:
    """Streams batches of CatalogSourceTrack from a local Parquet file with deltas merged."""
    limit = max_tracks if max_tracks and max_tracks > 0 else None
    effective_batch = min(batch_size, limit) if limit is not None else batch_size
    yielded = 0
    pf = pq.ParquetFile(tmp_path)
    for batch in pf.iter_batches(batch_size=effective_batch):
        parsed = _parse_records(batch.to_pylist())
        if limit is not None:
            parsed = parsed[: max(limit - yielded, 0)]
        if delta_map and parsed:
            parsed = [apply_delta_to_track(t, delta_map) for t in parsed]
            record_seen_keys(parsed, existing_sids, existing_keys)
        if parsed:
            yielded += len(parsed)
            yield parsed
        if limit is not None and yielded >= limit:
            break


__all__ = [
    "DELTA_PARQUET_SCHEMA",
    "_TrackDeltaItem",
    "_parse_records",
    "apply_delta_to_track",
    "apply_deltas_to_records",
    "build_delta_parquet_bytes",
    "compact_parquet_bytes",
    "delta_to_catalog_track",
    "iter_new_deltas",
    "iter_parquet_file_batches",
    "lookup_track_delta",
    "merge_delta_items",
    "parse_parquet_bytes",
    "read_deltas_from_bytes",
    "record_seen_keys",
    "resolve_compaction_schema",
]
