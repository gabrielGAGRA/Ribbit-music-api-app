"""Unit tests for GCSTrackCatalogAdapter and GCS Parquet ingestion."""

import io
from unittest.mock import MagicMock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from google.cloud import storage

from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.gcp.gcs_track_catalog import GCSTrackCatalogAdapter


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


def test_fetch_tracks_raises_external_service_error_when_bucket_not_configured() -> (
    None
):
    adapter = GCSTrackCatalogAdapter(bucket_name="")
    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.fetch_tracks()

    assert "bucket name is not configured" in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "GCP_GCS"


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

    assert "Failed to download" in str(exc_info.value)
    assert exc_info.value.details.get("bucket_name") == "music-catalog-bucket"


def test_parse_parquet_bytes_raises_external_service_error_on_corrupt_bytes() -> None:
    adapter = GCSTrackCatalogAdapter(bucket_name="test-bucket")
    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.parse_parquet_bytes(b"not a parquet file")

    assert "Failed to parse Parquet content" in str(exc_info.value)


def test_write_preview_delta_uploads_parquet() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/songs_final.parquet",
        storage_client=mock_client,
    )

    adapter.write_preview_delta(
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
        if name == "Songs/songs_final.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/songs_final.parquet",
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

    # Delta blob should have been deleted
    mock_delta_blob.delete.assert_called_once()

    # Version blob should have been updated to version 3
    mock_version_blob.upload_from_string.assert_called_once()
    version_payload = mock_version_blob.upload_from_string.call_args[0][0]
    assert '"version": 3' in version_payload


def test_write_track_delta_uploads_parquet_with_genre() -> None:
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/songs_final.parquet",
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
        if name == "Songs/songs_final.parquet":
            return mock_base_blob
        if name == "Songs/catalog_version.json":
            return mock_version_blob
        return MagicMock()

    mock_bucket.blob.side_effect = blob_side_effect
    mock_client.bucket.return_value = mock_bucket

    adapter = GCSTrackCatalogAdapter(
        bucket_name="music-catalog-bucket",
        file_path="Songs/songs_final.parquet",
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
