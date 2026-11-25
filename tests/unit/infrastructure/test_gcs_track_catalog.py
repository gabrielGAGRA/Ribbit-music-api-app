"""Unit tests for GCSTrackCatalogAdapter and GCS Parquet ingestion."""

import io
from typing import Any
from unittest.mock import MagicMock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import urllib3
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage

from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.gcp.gcs_track_catalog import (
    GCSTrackCatalogAdapter,
    _GCSHTTPAdapter,
)


def _build_test_parquet_bytes() -> bytes:
    data = {
        "title": ["Bohemian Rhapsody", "Smells Like Teen Spirit", ""],
        "artist": ["Queen", "Nirvana", "Unknown Artist"],
        "album": ["A Night at the Opera", "Nevermind", None],
        "duration_seconds": [354, 301, 100],
        "genre": ["Rock", "Grunge", "Pop"],
        "country": ["UK", "USA", None],
        "release_year": [1975, 1991, None],
        "cover_url": ["https://example.com/cover1.jpg", None, None],
        "spotify_id": ["spot-1", "spot-2", None],
        "itunes_preview_url": [None, "https://example.com/preview.mp3", None],
        "explicit": [False, False, False],
    }
    table = pa.Table.from_pydict(data)
    sink = io.BytesIO()
    pq.write_table(table, sink)
    return sink.getvalue()


def test_gcs_adapter_implements_protocol() -> None:
    adapter = GCSTrackCatalogAdapter(bucket_name="test-bucket")
    assert isinstance(adapter, TrackCatalogFilePort)


def test_fetch_tracks_downloads_and_parses_parquet() -> None:
    parquet_bytes = _build_test_parquet_bytes()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = parquet_bytes
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="tracks_v1.parquet",
        storage_client=mock_client,
    )

    tracks = adapter.fetch_tracks()

    # The empty title row should have been skipped
    assert len(tracks) == 2

    assert tracks[0].title == "Bohemian Rhapsody"
    assert tracks[0].artist == "Queen"
    assert tracks[0].album == "A Night at the Opera"
    assert tracks[0].duration_seconds == 354
    assert tracks[0].genre == "Rock"
    assert tracks[0].release_year == 1975
    assert tracks[0].itunes_preview_url is None

    assert tracks[1].title == "Smells Like Teen Spirit"
    assert tracks[1].artist == "Nirvana"
    assert tracks[1].itunes_preview_url == "https://example.com/preview.mp3"

    mock_client.bucket.assert_called_once_with("music-catalog-bucket")
    mock_bucket.blob.assert_called_once_with("tracks_v1.parquet")
    mock_blob.download_as_bytes.assert_called_once_with(timeout=30.0)


def test_fetch_tracks_raises_external_service_error_when_bucket_not_configured() -> (
    None
):
    adapter = GCSTrackCatalogAdapter(bucket_name="")
    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.fetch_tracks()

    assert "bucket name is not configured" in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details


def test_fetch_tracks_raises_external_service_error_on_download_failure() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.side_effect = RuntimeError("GCS 404: Not Found")
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="missing.parquet",
        storage_client=mock_client,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.fetch_tracks()

    assert "Failed to download catalog tracks from cloud storage." in str(
        exc_info.value
    )
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details
    assert "missing.parquet" not in str(exc_info.value)


def test_fetch_tracks_tolerates_delta_loading_failure() -> None:
    parquet_bytes = _build_test_parquet_bytes()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = parquet_bytes
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket
    mock_client.list_blobs.side_effect = GoogleAPIError(
        "GCS list_blobs connection error"
    )

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="tracks_v1.parquet",
        storage_client=mock_client,
    )

    tracks = adapter.fetch_tracks()
    assert len(tracks) == 2
    assert tracks[0].title == "Bohemian Rhapsody"
    assert tracks[1].title == "Smells Like Teen Spirit"


def test_parse_parquet_bytes_raises_external_service_error_on_corrupt_bytes() -> None:
    adapter = GCSTrackCatalogAdapter(bucket_name="test-bucket")
    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.parse_parquet_bytes(b"not a parquet file")

    assert "Failed to parse Parquet content from catalog file." in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details


def test_write_track_delta_uploads_parquet() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    adapter.write_track_delta(
        title="Song A",
        artist="Artist A",
        preview_url="https://preview.itunes.apple.com/song-a.mp3",
        spotify_id="spot-a",
    )

    mock_client.bucket.assert_called_once_with("music-catalog-bucket")
    mock_bucket.blob.assert_called_once()
    blob_name = mock_bucket.blob.call_args[0][0]
    assert blob_name.startswith("Songs/deltas/delta_")
    assert blob_name.endswith(".parquet")

    mock_blob.upload_from_string.assert_called_once()
    uploaded_bytes = mock_blob.upload_from_string.call_args[0][0]
    assert mock_blob.upload_from_string.call_args.kwargs.get("timeout") == 30.0
    table = pq.read_table(io.BytesIO(uploaded_bytes))
    records = table.to_pylist()
    assert len(records) == 1
    assert records[0]["title"] == "Song A"
    assert records[0]["artist"] == "Artist A"
    assert (
        records[0]["itunes_preview_url"]
        == "https://preview.itunes.apple.com/song-a.mp3"
    )
    assert records[0]["spotify_id"] == "spot-a"


def test_write_track_delta_raises_external_service_error_on_upload_failure() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.upload_from_string.side_effect = RuntimeError("GCS upload failure")
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.write_track_delta(
            title="Song Delta",
            artist="Artist Delta",
        )

    assert "Failed to write track delta to cloud storage." in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details


def test_get_catalog_version_defaults_to_1_when_absent() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
    )
    info = adapter.get_catalog_version()
    assert info.version == 1
    mock_blob.exists.assert_called_once_with(timeout=30.0)


def test_get_catalog_version_parses_existing_json() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_text.return_value = (
        '{"version": 4, "updated_at": "2026-10-28T12:00:00Z"}'
    )
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
    )
    info = adapter.get_catalog_version()
    assert info.version == 4
    assert info.updated_at == "2026-10-28T12:00:00Z"
    mock_blob.download_as_text.assert_called_once_with(timeout=30.0)


def test_get_catalog_version_raises_external_service_error_on_storage_failure() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.side_effect = RuntimeError("GCS connection timeout")
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.get_catalog_version()

    assert "Failed to read catalog version from cloud storage." in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details


def test_compact_catalog_merges_deltas_deletes_blobs_and_increments_version() -> None:
    base_parquet = _build_test_parquet_bytes()

    delta_data = {
        "title": ["Bohemian Rhapsody"],
        "artist": ["Queen"],
        "itunes_preview_url": ["https://itunes.com/bohemian.mp3"],
        "spotify_id": ["spot-1"],
        "updated_at": ["2026-10-28T12:00:00Z"],
    }
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(delta_data), sink)
    delta_bytes = sink.getvalue()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()

    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "Songs/deltas/delta_123.parquet"
    mock_delta_blob.download_as_bytes.return_value = delta_bytes

    mock_client.list_blobs.return_value = [mock_delta_blob]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet

    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = True
    mock_version_blob.download_as_text.return_value = '{"version": 2}'

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    new_version = adapter.compact_catalog()
    assert new_version == 3

    # Base blob should have been overwritten with merged data
    mock_base_blob.upload_from_string.assert_called_once()
    uploaded_base_bytes = mock_base_blob.upload_from_string.call_args[0][0]
    uploaded_table = pq.read_table(io.BytesIO(uploaded_base_bytes))
    records = uploaded_table.to_pylist()

    queen_record = next(r for r in records if r["artist"] == "Queen")
    assert queen_record["itunes_preview_url"] == "https://itunes.com/bohemian.mp3"

    # Delta blob should have been deleted with timeout
    mock_delta_blob.delete.assert_called_once_with(timeout=30.0)

    # Version blob should have been updated to version 3
    mock_version_blob.upload_from_string.assert_called_once()
    version_payload = mock_version_blob.upload_from_string.call_args[0][0]
    assert '"version": 3' in version_payload


def test_compact_catalog_raises_external_service_error_on_storage_failure() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_client.list_blobs.side_effect = RuntimeError("GCS storage unreachable")

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.compact_catalog()

    assert "Failed to compact catalog in cloud storage." in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details


def test_compact_catalog_tolerates_delta_delete_failure() -> None:
    base_parquet = _build_test_parquet_bytes()
    delta_data = {
        "title": ["Bohemian Rhapsody"],
        "artist": ["Queen"],
        "itunes_preview_url": ["https://itunes.com/bohemian.mp3"],
    }
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(delta_data), sink)
    delta_bytes = sink.getvalue()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "deltas/delta_1.parquet"
    mock_delta_blob.download_as_bytes.return_value = delta_bytes
    mock_delta_blob.delete.side_effect = RuntimeError("Delete permission denied")
    mock_client.list_blobs.return_value = [mock_delta_blob]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet
    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = True
    mock_version_blob.download_as_text.return_value = '{"version": 1}'

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    new_version = adapter.compact_catalog()
    assert new_version == 2


def test_write_track_delta_uploads_parquet_with_genre() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    adapter.write_track_delta(
        title="Song B",
        artist="Artist B",
        preview_url="https://preview.itunes.apple.com/song-b.mp3",
        genre="Indie Rock",
        spotify_id="spot-b",
    )

    mock_client.bucket.assert_called_once_with("music-catalog-bucket")
    mock_bucket.blob.assert_called_once()
    mock_blob.upload_from_string.assert_called_once()
    uploaded_bytes = mock_blob.upload_from_string.call_args[0][0]
    table = pq.read_table(io.BytesIO(uploaded_bytes))
    records = table.to_pylist()
    assert len(records) == 1
    assert records[0]["title"] == "Song B"
    assert records[0]["artist"] == "Artist B"
    assert (
        records[0]["itunes_preview_url"]
        == "https://preview.itunes.apple.com/song-b.mp3"
    )
    assert records[0]["genre"] == "Indie Rock"
    assert records[0]["spotify_id"] == "spot-b"


def test_compact_catalog_merges_genre_from_delta() -> None:
    base_parquet = _build_test_parquet_bytes()

    delta_data = {
        "title": ["Smells Like Teen Spirit"],
        "artist": ["Nirvana"],
        "itunes_preview_url": ["https://itunes.com/nirvana.mp3"],
        "genre": ["Alternative Rock"],
        "spotify_id": ["spot-2"],
        "updated_at": ["2026-10-28T12:00:00Z"],
    }
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(delta_data), sink)
    delta_bytes = sink.getvalue()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()

    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "Songs/deltas/delta_456.parquet"
    mock_delta_blob.download_as_bytes.return_value = delta_bytes

    mock_client.list_blobs.return_value = [mock_delta_blob]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet

    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = True
    mock_version_blob.download_as_text.return_value = '{"version": 1}'

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    new_version = adapter.compact_catalog()
    assert new_version == 2

    mock_base_blob.upload_from_string.assert_called_once()
    uploaded_base_bytes = mock_base_blob.upload_from_string.call_args[0][0]
    uploaded_table = pq.read_table(io.BytesIO(uploaded_base_bytes))
    records = uploaded_table.to_pylist()

    nirvana_record = next(r for r in records if r["artist"] == "Nirvana")
    assert nirvana_record["genre"] == "Alternative Rock"
    assert nirvana_record["itunes_preview_url"] == "https://itunes.com/nirvana.mp3"


def test_write_fetch_and_compact_track_delta_handles_cover_url() -> None:
    base_parquet = _build_test_parquet_bytes()

    delta_data = {
        "title": ["Smells Like Teen Spirit"],
        "artist": ["Nirvana"],
        "itunes_preview_url": [None],
        "genre": [None],
        "cover_url": ["https://is1-ssl.mzstatic.com/image/100x100bb.jpg"],
        "spotify_id": ["spot-2"],
        "updated_at": ["2026-11-10T23:30:00Z"],
    }
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(delta_data), sink)
    delta_bytes = sink.getvalue()

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()

    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "Songs/deltas/delta_cover.parquet"
    mock_delta_blob.download_as_bytes.return_value = delta_bytes

    mock_client.list_blobs.return_value = [mock_delta_blob]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet

    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = True
    mock_version_blob.download_as_text.return_value = '{"version": 1}'

    mock_write_blob = MagicMock()

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return mock_write_blob

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    # 1. Write delta with cover_url
    adapter.write_track_delta(
        title="Smells Like Teen Spirit",
        artist="Nirvana",
        cover_url="https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
        spotify_id="spot-2",
    )
    written_table = pq.read_table(
        io.BytesIO(mock_write_blob.upload_from_string.call_args[0][0])
    )
    assert (
        written_table.to_pylist()[0]["cover_url"]
        == "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    )

    # 2. Fetch tracks merges pending delta cover_url
    fetched = adapter.fetch_tracks()
    nirvana_fetched = next(t for t in fetched if t.artist == "Nirvana")
    assert (
        nirvana_fetched.cover_url == "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    )

    # 3. Compact catalog persists cover_url into base Parquet
    new_version = adapter.compact_catalog()
    assert new_version == 2
    compacted_table = pq.read_table(
        io.BytesIO(mock_base_blob.upload_from_string.call_args[0][0])
    )
    nirvana_compacted = next(
        r for r in compacted_table.to_pylist() if r["artist"] == "Nirvana"
    )
    assert (
        nirvana_compacted["cover_url"]
        == "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    )


def _parquet_bytes(data: dict[str, list[object]]) -> bytes:
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(data), sink)
    return sink.getvalue()


@pytest.mark.parametrize(
    "base_data",
    [
        # All-null cover_url column (pa.null() schema type)
        {
            "title": ["Song One", "Song Two"],
            "artist": ["Artist One", "Artist Two"],
            "itunes_preview_url": [None, None],
            "genre": ["Rock", "Pop"],
            "cover_url": [None, None],
            "spotify_id": ["spot-1", "spot-2"],
        },
        # Missing cover_url column entirely
        {
            "title": ["Song One", "Song Two"],
            "artist": ["Artist One", "Artist Two"],
            "itunes_preview_url": [None, None],
            "genre": ["Rock", "Pop"],
            "spotify_id": ["spot-1", "spot-2"],
        },
    ],
)
def test_compact_catalog_handles_null_and_missing_cover_url_column(
    base_data: dict[str, list[object]],
) -> None:
    base_parquet = _parquet_bytes(base_data)
    delta_bytes = _parquet_bytes(
        {
            "title": ["Song One"],
            "artist": ["Artist One"],
            "itunes_preview_url": [None],
            "genre": [None],
            "cover_url": ["https://is1-ssl.mzstatic.com/image/100x100bb.jpg"],
            "spotify_id": ["spot-1"],
            "updated_at": ["2026-11-10T23:35:00Z"],
        }
    )

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "Songs/deltas/delta_null_col.parquet"
    mock_delta_blob.download_as_bytes.return_value = delta_bytes
    mock_client.list_blobs.return_value = [mock_delta_blob]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet
    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = False

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )
    new_version = adapter.compact_catalog()
    assert new_version == 2

    compacted_table = pq.read_table(
        io.BytesIO(mock_base_blob.upload_from_string.call_args[0][0])
    )
    row_one = next(r for r in compacted_table.to_pylist() if r["title"] == "Song One")
    assert row_one["cover_url"] == "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"


def test_fetch_and_compact_merge_split_key_deltas_across_blobs() -> None:
    base_parquet = _build_test_parquet_bytes()
    blob_1_bytes = _parquet_bytes(
        {
            "title": ["Smells Like Teen Spirit"],
            "artist": ["Nirvana"],
            "itunes_preview_url": ["https://itunes.com/nirvana-new.m4a"],
            "genre": [None],
            "cover_url": [None],
            "spotify_id": ["spot-2"],
            "updated_at": ["2026-11-10T23:35:00Z"],
        }
    )
    blob_2_bytes = _parquet_bytes(
        {
            "title": ["Smells Like Teen Spirit"],
            "artist": ["Nirvana"],
            "itunes_preview_url": [None],
            "genre": [None],
            "cover_url": ["https://is1-ssl.mzstatic.com/image/nirvana.jpg"],
            "spotify_id": [None],
            "updated_at": ["2026-11-10T23:36:00Z"],
        }
    )

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    blob_1 = MagicMock()
    blob_1.name = "Songs/deltas/delta_1.parquet"
    blob_1.download_as_bytes.return_value = blob_1_bytes
    blob_2 = MagicMock()
    blob_2.name = "Songs/deltas/delta_2.parquet"
    blob_2.download_as_bytes.return_value = blob_2_bytes
    mock_client.list_blobs.return_value = [blob_1, blob_2]

    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet
    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = False

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    fetched = adapter.fetch_tracks()
    nirvana = next(t for t in fetched if t.artist == "Nirvana")
    assert nirvana.itunes_preview_url == "https://itunes.com/nirvana-new.m4a"
    assert nirvana.cover_url == "https://is1-ssl.mzstatic.com/image/nirvana.jpg"

    adapter.compact_catalog()
    compacted_table = pq.read_table(
        io.BytesIO(mock_base_blob.upload_from_string.call_args[0][0])
    )
    nirvana_row = next(
        r for r in compacted_table.to_pylist() if r["artist"] == "Nirvana"
    )
    assert nirvana_row["itunes_preview_url"] == "https://itunes.com/nirvana-new.m4a"
    assert nirvana_row["cover_url"] == "https://is1-ssl.mzstatic.com/image/nirvana.jpg"


def test_get_client_caches_client(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_instance = MagicMock(spec=storage.Client)
    client_calls = 0

    def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal client_calls
        client_calls += 1
        return mock_instance

    monkeypatch.setattr(storage, "Client", mock_client_factory)
    adapter = GCSTrackCatalogAdapter(bucket_name="test-bucket")
    c1 = adapter._get_client()
    c2 = adapter._get_client()
    assert c1 is c2
    assert client_calls == 1


def test_get_client_raises_external_service_error_without_leaking_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_init(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("GCP auth credentials failed: secret_123")

    monkeypatch.setattr(storage, "Client", mock_init)
    adapter = GCSTrackCatalogAdapter(
        bucket_name="secret-bucket",
        file_path="secret-path.parquet",
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter._get_client()

    assert "Failed to initialize cloud storage client." in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"
    assert "bucket_name" not in exc_info.value.details
    assert "file_path" not in exc_info.value.details
    assert "secret" not in str(exc_info.value)


def test_gcs_adapter_custom_timeout_passed_to_io_calls() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = _build_test_parquet_bytes()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket
    mock_client.list_blobs.return_value = []

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        storage_client=mock_client,
        timeout=15.0,
    )
    adapter.fetch_tracks()
    mock_blob.download_as_bytes.assert_called_once_with(timeout=15.0)


def test_write_track_delta_matches_tracks_schema_and_fetch_tracks_includes_new_track() -> (
    None
):
    base_parquet = _build_test_parquet_bytes()

    uploaded_deltas: list[bytes] = []

    def upload_delta(data: bytes, **kwargs: Any) -> None:
        uploaded_deltas.append(data)

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet

    mock_delta_upload_blob = MagicMock()
    mock_delta_upload_blob.upload_from_string.side_effect = upload_delta

    def blob_side_effect(name: str) -> MagicMock:
        if name == "Songs/tracks.parquet":
            return mock_base_blob
        return mock_delta_upload_blob

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )
    adapter.write_track_delta(
        title="Brand New Track",
        artist="New Artist",
        preview_url="https://itunes.example.com/new.m4a",
        genre="Synthwave",
        cover_url="https://itunes.example.com/new.jpg",
        spotify_id="sp-brand-new",
        album="New Album",
        duration_seconds=242,
        country="Brazil",
        release_year=2025,
        explicit=False,
        is_deleted=False,
        created_at="2026-11-12T19:50:00+00:00",
    )

    assert len(uploaded_deltas) == 1
    delta_table = pq.read_table(io.BytesIO(uploaded_deltas[0]))
    assert delta_table.schema.names == [
        "spotify_id",
        "title",
        "artist",
        "duration_seconds",
        "genre",
        "country",
        "release_year",
        "cover_url",
        "itunes_preview_url",
        "explicit",
        "is_deleted",
        "created_at",
    ]

    mock_delta_blob = MagicMock()
    mock_delta_blob.name = "Songs/deltas/delta_new.parquet"
    mock_delta_blob.download_as_bytes.return_value = uploaded_deltas[0]
    mock_client.list_blobs.return_value = [mock_delta_blob]

    tracks = adapter.fetch_tracks()
    new_track = next(t for t in tracks if t.spotify_id == "sp-brand-new")
    assert new_track.title == "Brand New Track"
    assert new_track.album is None
    assert new_track.duration_seconds == 242
    assert new_track.genre == "Synthwave"
    assert new_track.country == "Brazil"
    assert new_track.release_year == 2025
    assert new_track.cover_url == "https://itunes.example.com/new.jpg"
    assert new_track.itunes_preview_url == "https://itunes.example.com/new.m4a"


def test_iter_track_batches_respects_max_tracks_and_filters_partial_deltas() -> None:
    from pathlib import Path

    base_parquet = _build_test_parquet_bytes()
    delta_1_bytes = _parquet_bytes(
        {
            "title": ["Bohemian Rhapsody"],
            "artist": ["Queen"],
            "itunes_preview_url": ["https://audio-ssl.itunes.apple.com/queen.m4a"],
            "cover_url": ["https://is1-ssl.mzstatic.com/queen.jpg"],
            "spotify_id": ["spot-1"],
        }
    )
    # Full standalone delta (includes duration_seconds and explicit) should be ingested
    delta_2_bytes = _parquet_bytes(
        {
            "title": ["Extra Delta Track"],
            "artist": ["Delta Artist"],
            "duration_seconds": [215],
            "explicit": [True],
            "itunes_preview_url": ["https://audio-ssl.itunes.apple.com/extra.m4a"],
            "cover_url": ["https://is1-ssl.mzstatic.com/extra.jpg"],
            "spotify_id": ["spot-extra"],
        }
    )
    # Partial update delta for an explicit track beyond max_tracks must NOT become a new track
    delta_partial_bytes = _parquet_bytes(
        {
            "title": ["Explicit Beyond Limit"],
            "artist": ["Restricted Artist"],
            "genre": ["Hip-Hop"],
            "duration_seconds": [None],
            "explicit": [None],
            "spotify_id": ["spot-beyond"],
        }
    )

    def _write_base(dest_path: str, **_kwargs: Any) -> None:
        Path(dest_path).write_bytes(base_parquet)

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_base_blob = MagicMock()
    mock_base_blob.download_to_filename.side_effect = _write_base
    mock_bucket.blob.return_value = mock_base_blob
    mock_client.bucket.return_value = mock_bucket

    blob_1 = MagicMock()
    blob_1.name = "Songs/deltas/d1.parquet"
    blob_1.download_as_bytes.return_value = delta_1_bytes
    blob_2 = MagicMock()
    blob_2.name = "Songs/deltas/d2.parquet"
    blob_2.download_as_bytes.return_value = delta_2_bytes
    blob_3 = MagicMock()
    blob_3.name = "Songs/deltas/d3_partial.parquet"
    blob_3.download_as_bytes.return_value = delta_partial_bytes
    mock_client.list_blobs.return_value = [blob_1, blob_2, blob_3]

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
        max_tracks=1,
    )

    batches = list(adapter.iter_track_batches(batch_size=10))
    assert len(batches) == 2
    assert len(batches[0]) == 1
    assert batches[0][0].title == "Bohemian Rhapsody"
    assert batches[0][0].cover_url == "https://is1-ssl.mzstatic.com/queen.jpg"
    assert len(batches[1]) == 1
    assert batches[1][0].title == "Extra Delta Track"
    assert batches[1][0].explicit is True
    assert batches[1][0].duration_seconds == 215


def test_fetch_tracks_skips_missing_delta_blob_without_dropping_other_deltas() -> None:
    from google.api_core.exceptions import NotFound

    base_parquet = _build_test_parquet_bytes()
    valid_delta = _parquet_bytes(
        {
            "title": ["Bohemian Rhapsody"],
            "artist": ["Queen"],
            "itunes_preview_url": ["https://audio-ssl.itunes.apple.com/queen.m4a"],
            "spotify_id": ["spot-1"],
        }
    )

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet
    mock_bucket.blob.return_value = mock_base_blob
    mock_client.bucket.return_value = mock_bucket

    missing_blob = MagicMock()
    missing_blob.name = "Songs/deltas/d_gone.parquet"
    missing_blob.download_as_bytes.side_effect = NotFound("compacted concurrently")

    ok_blob = MagicMock()
    ok_blob.name = "Songs/deltas/d_ok.parquet"
    ok_blob.download_as_bytes.return_value = valid_delta
    mock_client.list_blobs.return_value = [missing_blob, ok_blob]

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )

    tracks = adapter.fetch_tracks()
    queen = next(t for t in tracks if t.title == "Bohemian Rhapsody")
    assert queen.itunes_preview_url == "https://audio-ssl.itunes.apple.com/queen.m4a"


def test_delta_merge_orders_chronologically_and_preserves_known_genre() -> None:
    base_parquet = _build_test_parquet_bytes()
    newer_delta = _parquet_bytes(
        {
            "spotify_id": ["sp-1"],
            "title": ["Bohemian Rhapsody"],
            "artist": ["Queen"],
            "genre": ["Classic Rock"],
            "country": ["GB"],
            "created_at": ["2026-11-19T12:00:00+00:00"],
        }
    )
    older_delta = _parquet_bytes(
        {
            "spotify_id": ["sp-1"],
            "title": ["Bohemian Rhapsody"],
            "artist": ["Queen"],
            "genre": ["Pop"],
            "country": ["USA"],
            "created_at": ["2026-11-18T12:00:00+00:00"],
        }
    )
    unknown_latest = _parquet_bytes(
        {
            "spotify_id": ["sp-1"],
            "title": ["Bohemian Rhapsody"],
            "artist": ["Queen"],
            "genre": ["Unknown"],
            "created_at": ["2026-11-19T13:00:00+00:00"],
        }
    )

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_parquet
    mock_bucket.blob.return_value = mock_base_blob
    mock_client.bucket.return_value = mock_bucket

    # Intentionally place newer delta first with alphabetically earlier filename.
    blob_newer = MagicMock()
    blob_newer.name = "Songs/deltas/delta_aaaa.parquet"
    blob_newer.download_as_bytes.return_value = newer_delta

    blob_older = MagicMock()
    blob_older.name = "Songs/deltas/delta_zzzz.parquet"
    blob_older.download_as_bytes.return_value = older_delta

    blob_unknown = MagicMock()
    blob_unknown.name = "Songs/deltas/delta_mmmm.parquet"
    blob_unknown.download_as_bytes.return_value = unknown_latest

    mock_client.list_blobs.return_value = [blob_newer, blob_older, blob_unknown]

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )
    tracks = adapter.fetch_tracks()
    queen = next(t for t in tracks if t.title == "Bohemian Rhapsody")
    assert queen.genre == "Classic Rock"
    assert queen.country == "GB"


def test_compact_catalog_streams_large_string_schema_assigns_track_id_and_applies_full_updates() -> (
    None
):
    base_schema = pa.schema(
        [
            pa.field("track_id", pa.int64()),
            pa.field("spotify_id", pa.large_string()),
            pa.field("title", pa.large_string()),
            pa.field("artist", pa.large_string()),
            pa.field("album", pa.large_string()),
            pa.field("duration_seconds", pa.int64()),
            pa.field("genre", pa.large_string()),
            pa.field("country", pa.large_string()),
            pa.field("release_year", pa.int64()),
            pa.field("cover_url", pa.large_string()),
            pa.field("itunes_preview_url", pa.large_string()),
            pa.field("explicit", pa.int64()),
            pa.field("is_deleted", pa.int64()),
            pa.field("created_at", pa.large_string()),
        ]
    )
    base_table = pa.Table.from_pylist(
        [
            {
                "track_id": 100,
                "spotify_id": "sp-existing",
                "title": "Existing Song",
                "artist": "Existing Artist",
                "album": "Old Album",
                "duration_seconds": 200,
                "genre": "Unknown",
                "country": "USA",
                "release_year": 2020,
                "cover_url": None,
                "itunes_preview_url": None,
                "explicit": 0,
                "is_deleted": 0,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "track_id": 101,
                "spotify_id": "sp-to-delete",
                "title": "Delete Me",
                "artist": "Old Artist",
                "album": "Alb",
                "duration_seconds": 180,
                "genre": "Pop",
                "country": "US",
                "release_year": 2019,
                "cover_url": None,
                "itunes_preview_url": None,
                "explicit": 0,
                "is_deleted": 0,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
        ],
        schema=base_schema,
    )
    buf = io.BytesIO()
    pq.write_table(base_table, buf)
    base_bytes = buf.getvalue()

    update_delta = _parquet_bytes(
        {
            "spotify_id": ["sp-existing"],
            "title": ["Existing Song"],
            "artist": ["Existing Artist"],
            "genre": ["Forró"],
            "country": ["BR"],
            "explicit": [1],
            "created_at": ["2026-11-19T12:00:00+00:00"],
        }
    )
    delete_delta = _parquet_bytes(
        {
            "spotify_id": ["sp-to-delete"],
            "title": ["Delete Me"],
            "artist": ["Old Artist"],
            "is_deleted": [1],
            "created_at": ["2026-11-19T12:01:00+00:00"],
        }
    )
    new_track_delta = _parquet_bytes(
        {
            "spotify_id": ["sp-brand-new"],
            "title": ["Utopia"],
            "artist": ["Delights"],
            "album": ["Utopia EP"],
            "duration_seconds": [210],
            "genre": ["Indie"],
            "country": [None],
            "release_year": [2024],
            "cover_url": ["https://img.example.com/utopia.jpg"],
            "itunes_preview_url": ["https://audio.example.com/utopia.m4a"],
            "explicit": [0],
            "is_deleted": [0],
            "created_at": ["2026-11-19T12:02:00+00:00"],
        }
    )

    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_base_blob = MagicMock()
    mock_base_blob.download_as_bytes.return_value = base_bytes
    mock_version_blob = MagicMock()
    mock_version_blob.exists.return_value = False

    def _get_blob(name: str) -> MagicMock:
        if name.endswith("catalog_version.json"):
            return mock_version_blob
        return mock_base_blob

    mock_bucket.blob.side_effect = _get_blob
    mock_client.bucket.return_value = mock_bucket

    b1, b2, b3 = MagicMock(), MagicMock(), MagicMock()
    b1.name = "Songs/deltas/delta_1.parquet"
    b1.download_as_bytes.return_value = update_delta
    b2.name = "Songs/deltas/delta_2.parquet"
    b2.download_as_bytes.return_value = delete_delta
    b3.name = "Songs/deltas/delta_3.parquet"
    b3.download_as_bytes.return_value = new_track_delta
    mock_client.list_blobs.return_value = [b1, b2, b3]

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/tracks.parquet",
        storage_client=mock_client,
    )
    new_version = adapter.compact_catalog()
    assert new_version == 2

    compacted_bytes = mock_base_blob.upload_from_string.call_args[0][0]
    assert (
        pq.ParquetFile(io.BytesIO(compacted_bytes))
        .metadata.row_group(0)
        .column(0)
        .compression
        == "ZSTD"
    )
    compacted_table = pq.read_table(io.BytesIO(compacted_bytes))
    assert compacted_table.schema.equals(base_schema)
    rows = {r["spotify_id"]: r for r in compacted_table.to_pylist()}
    assert rows["sp-existing"]["genre"] == "Forró"
    assert rows["sp-existing"]["country"] == "BR"
    assert rows["sp-existing"]["explicit"] == 1
    assert rows["sp-to-delete"]["is_deleted"] == 1
    assert rows["sp-brand-new"]["track_id"] == 102
    assert rows["sp-brand-new"]["is_deleted"] == 0
    assert rows["sp-brand-new"]["created_at"] == "2026-11-19T12:02:00+00:00"


def test_get_client_mounts_http11_adapter_disabling_http2_and_http3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_http = MagicMock()
    mock_instance = MagicMock(spec=storage.Client)
    mock_instance._http = mock_http
    monkeypatch.setattr(storage, "Client", lambda *args, **kwargs: mock_instance)

    adapter = GCSTrackCatalogAdapter(bucket_name="test-bucket")
    client = adapter._get_client()

    assert client is mock_instance
    mock_http.mount.assert_called_once()
    prefix, mounted_adapter = mock_http.mount.call_args[0]
    assert prefix == "https://"
    assert isinstance(mounted_adapter, _GCSHTTPAdapter)

    captured_kwargs: dict[str, Any] = {}

    def fake_super_init(
        self_adapter: _GCSHTTPAdapter,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> None:
        captured_kwargs.update(pool_kwargs)

    monkeypatch.setattr(_GCSHTTPAdapter.__mro__[1], "init_poolmanager", fake_super_init)
    mounted_adapter.init_poolmanager(16, 16)
    http_version = getattr(urllib3, "HttpVersion", None)
    assert http_version is not None
    assert captured_kwargs["disabled_svn"] == {http_version.h2, http_version.h3}


def test_delete_delta_blobs_deletes_multiple_blobs_and_tolerates_failure() -> None:
    b1, b2, b3 = MagicMock(), MagicMock(), MagicMock()
    b1.name = "deltas/1.parquet"
    b2.name = "deltas/2.parquet"
    b3.name = "deltas/3.parquet"
    b2.delete.side_effect = RuntimeError("transient error")

    adapter = GCSTrackCatalogAdapter(
        bucket_name="test-bucket",
        storage_client=MagicMock(spec=storage.Client),
    )
    adapter._delete_delta_blobs([b1, b2, b3])

    b1.delete.assert_called_once()
    b2.delete.assert_called_once()
    b3.delete.assert_called_once()
