"""Unit tests for IngestTracksFromCatalogUseCase."""

import sqlite3
from unittest.mock import MagicMock

from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    TrackCatalogFilePort,
)
from app.application.use_cases.admin.ingest_tracks import (
    IngestTracksFromCatalogUseCase,
)
from app.infrastructure.repositories.connection import SCHEMA_PATH
from app.infrastructure.repositories.track_repository import SQLiteTrackRepository


def _create_in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def test_ingest_tracks_inserts_new_tracks_into_empty_repo() -> None:
    conn = _create_in_memory_db()
    repo = SQLiteTrackRepository(conn)

    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.fetch_tracks.return_value = [
        CatalogSourceTrack(
            title="Song A",
            artist="Artist 1",
            duration_seconds=200,
            genre="Rock",
            album="Album 1",
            cover_url="https://example.com/cover1.jpg",
            spotify_id="spotify-1",
        ),
        CatalogSourceTrack(
            title="Song B",
            artist="Artist 2",
            duration_seconds=180,
            genre="Pop",
        ),
    ]

    use_case = IngestTracksFromCatalogUseCase(
        track_repo=repo,
        catalog_file_port=mock_catalog,
    )

    result = use_case.execute()

    assert result.total_processed == 2
    assert result.inserted == 2
    assert result.updated == 0

    assert repo.count_all() == 2
    track_a = repo.find_by_spotify_id("spotify-1")
    assert track_a is not None
    assert track_a.title == "Song A"
    assert track_a.artist == "Artist 1"
    assert track_a.album == "Album 1"

    track_b = repo.find_by_title_and_artist("Song B", "Artist 2")
    assert track_b is not None
    assert track_b.genre == "Pop"


def test_ingest_tracks_idempotent_and_updates_missing_metadata() -> None:
    conn = _create_in_memory_db()
    repo = SQLiteTrackRepository(conn)

    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    # First batch: minimal metadata
    mock_catalog.fetch_tracks.return_value = [
        CatalogSourceTrack(
            title="Song A",
            artist="Artist 1",
            duration_seconds=200,
            genre="Rock",
            spotify_id="spotify-1",
        ),
    ]

    use_case = IngestTracksFromCatalogUseCase(
        track_repo=repo,
        catalog_file_port=mock_catalog,
    )
    res1 = use_case.execute()
    assert res1.inserted == 1
    assert res1.updated == 0

    # Second batch: same song, now with cover and itunes preview enriched
    mock_catalog.fetch_tracks.return_value = [
        CatalogSourceTrack(
            title="Song A",
            artist="Artist 1",
            duration_seconds=200,
            genre="Rock",
            spotify_id="spotify-1",
            cover_url="https://example.com/new_cover.jpg",
            itunes_preview_url="https://example.com/new_preview.mp3",
        ),
    ]

    res2 = use_case.execute()
    assert res2.inserted == 0
    assert res2.updated == 1
    assert repo.count_all() == 1

    updated = repo.find_by_spotify_id("spotify-1")
    assert updated is not None
    assert updated.cover_url == "https://example.com/new_cover.jpg"
    assert updated.itunes_preview_url == "https://example.com/new_preview.mp3"


def test_ingest_tracks_updates_missing_genre() -> None:
    conn = _create_in_memory_db()
    repo = SQLiteTrackRepository(conn)

    mock_catalog = MagicMock(spec=TrackCatalogFilePort)
    mock_catalog.fetch_tracks.return_value = [
        CatalogSourceTrack(
            title="Song No Genre",
            artist="Artist X",
            duration_seconds=200,
            genre=None,
            spotify_id="spot-x",
        ),
    ]

    use_case = IngestTracksFromCatalogUseCase(
        track_repo=repo,
        catalog_file_port=mock_catalog,
    )
    res1 = use_case.execute()
    assert res1.inserted == 1

    mock_catalog.fetch_tracks.return_value = [
        CatalogSourceTrack(
            title="Song No Genre",
            artist="Artist X",
            duration_seconds=200,
            genre="Synthwave",
            spotify_id="spot-x",
        ),
    ]
    res2 = use_case.execute()
    assert res2.updated == 1

    track = repo.find_by_spotify_id("spot-x")
    assert track is not None
    assert track.genre == "Synthwave"
