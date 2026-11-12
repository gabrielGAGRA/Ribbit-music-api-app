"""Unit tests for SQLiteUserStatsRepository analytical queries."""

import sqlite3
lazy from collections.abc import Iterator

import pytest

from app.infrastructure.repositories import SCHEMA_PATH, SQLiteUserStatsRepository


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.commit()
    yield connection
    connection.close()


def _seed_user_and_catalog(conn: sqlite3.Connection) -> tuple[int, int]:
    conn.execute(
        "INSERT INTO plans (name, monthly_price, max_profiles) VALUES ('Premium', 19.9, 1)"
    )
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, age, plan_id, created_at)
        VALUES ('u1@test.com', 'hash', 'User One', 25, 1, '2025-01-01T00:00:00+00:00'),
               ('u2@test.com', 'hash', 'User Two', 28, 1, '2025-01-01T00:00:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO tracks (title, artist, duration_seconds, genre, release_year, is_deleted, created_at)
        VALUES
            ('T1', 'Artist A', 200, 'Rock', 2020, 0, '2025-01-01T00:00:00+00:00'),
            ('T2', 'Artist A', 180, 'Rock', 2020, 0, '2025-01-01T00:00:00+00:00'),
            ('T3', 'Artist B', 210, 'Indie', 2018, 0, '2025-01-01T00:00:00+00:00'),
            ('T4', 'Artist C', 190, 'unknown', 2022, 0, '2025-01-01T00:00:00+00:00'),
            ('T5', 'Artist D', 240, 'Jazz', 2015, 1, '2025-01-01T00:00:00+00:00'),
            ('T6', 'Artist B', 230, 'Pop', 2024, 0, '2025-01-01T00:00:00+00:00')
        """
    )
    # User 1 interactions across 2025 and 2026
    conn.execute(
        """
        INSERT INTO interactions (user_id, track_id, action, created_at, source)
        VALUES
            (1, 1, 'like', '2026-03-10T12:00:00+00:00', 'discovery'),
            (1, 2, 'superlike', '2026-03-15T12:00:00+00:00', 'jam'),
            (1, 3, 'dislike', '2026-05-01T12:00:00+00:00', 'discovery'),
            (1, 4, 'like', '2026-05-02T12:00:00+00:00', ''),
            (1, 5, 'superlike', '2026-05-03T12:00:00+00:00', 'search'),
            (1, 6, 'superlike', '2025-11-20T12:00:00+00:00', 'playlist'),
            (2, 1, 'dislike', '2026-01-01T12:00:00+00:00', 'discovery')
        """
    )
    # Reviews (1 active in 2026, 1 deleted in 2026, 1 active in 2025)
    conn.execute(
        """
        INSERT INTO reviews (user_id, track_id, rating, text, is_deleted, created_at)
        VALUES
            (1, 1, 5, 'Great', 0, '2026-03-10T12:00:00+00:00'),
            (1, 2, 1, 'Deleted', 1, '2026-03-11T12:00:00+00:00'),
            (1, 6, 4, 'Nice', 0, '2025-11-21T12:00:00+00:00')
        """
    )
    # Playlists
    conn.execute(
        """
        INSERT INTO playlists (user_id, name, created_at)
        VALUES
            (1, 'P2026', '2026-04-01T00:00:00+00:00'),
            (1, 'P2025', '2025-12-01T00:00:00+00:00')
        """
    )
    # Jams and participants
    conn.execute(
        """
        INSERT INTO jams (host_user_id, room_name, room_code, created_at)
        VALUES
            (2, 'Room 1', 'CODE1', '2026-02-01T00:00:00+00:00'),
            (2, 'Room 2', 'CODE2', '2025-10-01T00:00:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO jam_participants (jam_id, user_id, joined_at)
        VALUES
            (1, 1, '2026-02-01T01:00:00+00:00'),
            (2, 1, '2025-10-01T01:00:00+00:00')
        """
    )
    conn.commit()
    return 1, 2


def test_user_stats_empty_user_returns_zeros(conn: sqlite3.Connection) -> None:
    _seed_user_and_catalog(conn)
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, age, plan_id, created_at)
        VALUES ('empty@test.com', 'hash', 'Empty', 22, 1, '2026-01-01T00:00:00+00:00')
        """
    )
    conn.commit()
    repo = SQLiteUserStatsRepository(conn)

    stats = repo.get_user_stats(user_id=3)

    assert stats.user_id == 3
    assert stats.year is None
    assert stats.available_years == []
    assert stats.total_interactions == 0
    assert stats.total_likes == 0
    assert stats.total_superlikes == 0
    assert stats.total_dislikes == 0
    assert stats.positive_rate == 0.0
    assert stats.top_genres == []
    assert stats.top_artists == []
    assert stats.by_interaction_year == []
    assert stats.by_month == []
    assert stats.by_release_year == []
    assert stats.by_source == []
    assert stats.total_reviews == 0
    assert stats.average_rating == 0.0
    assert stats.total_playlists == 0
    assert stats.total_jams_participated == 0


def test_user_stats_all_years_aggregations(conn: sqlite3.Connection) -> None:
    user_id, _ = _seed_user_and_catalog(conn)
    repo = SQLiteUserStatsRepository(conn)

    stats = repo.get_user_stats(user_id=user_id)

    assert stats.year is None
    assert stats.available_years == [2026, 2025]
    assert stats.total_interactions == 6
    assert stats.total_likes == 2
    assert stats.total_superlikes == 3
    assert stats.total_dislikes == 1
    assert stats.positive_rate == round(5 / 6, 4)

    # Top genres excludes 'unknown' and deleted track 'Jazz'
    assert [g.genre for g in stats.top_genres] == ["rock", "pop", "indie"]
    assert stats.top_genres[0].likes == 1
    assert stats.top_genres[0].superlikes == 1
    assert stats.top_genres[0].total_positive == 2

    # Top artists excludes deleted track 'Artist D'
    assert stats.top_artists[0].artist == "Artist A"
    assert stats.top_artists[0].total_positive == 2

    # Yearly breakdown
    assert [(y.year, y.total, y.superlikes) for y in stats.by_interaction_year] == [
        (2026, 5, 2),
        (2025, 1, 1),
    ]

    # Release year breakdown (only positive non-deleted tracks with release_year)
    assert [r.release_year for r in stats.by_release_year] == [2024, 2022, 2020]
    assert stats.by_release_year[2].total_positive == 2

    # Source breakdown maps empty string to 'unknown'
    sources = {s.source: s for s in stats.by_source}
    assert sources["discovery"].likes == 1
    assert sources["discovery"].dislikes == 1
    assert sources["unknown"].likes == 1

    # Community & library counts
    assert stats.total_reviews == 2
    assert stats.average_rating == 4.5
    assert stats.total_playlists == 2
    assert stats.total_jams_participated == 2


def test_user_stats_filtered_by_year(conn: sqlite3.Connection) -> None:
    user_id, _ = _seed_user_and_catalog(conn)
    repo = SQLiteUserStatsRepository(conn)

    stats = repo.get_user_stats(user_id=user_id, year=2026)

    assert stats.year == 2026
    assert stats.available_years == [2026, 2025]
    assert stats.total_interactions == 5
    assert stats.total_likes == 2
    assert stats.total_superlikes == 2
    assert stats.total_dislikes == 1
    assert [(m.month, m.total) for m in stats.by_month] == [(3, 2), (5, 3)]
    assert [g.genre for g in stats.top_genres] == ["rock", "indie"]
    assert stats.total_reviews == 1
    assert stats.average_rating == 5.0
    assert stats.total_playlists == 1
    assert stats.total_jams_participated == 1
