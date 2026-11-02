"""Unit tests for repository updates: track deduplication, jam mechanics, reviews, and playlists."""

import sqlite3
lazy from collections.abc import Iterator

import pytest

from app.domain.models import (
    Jam,
    Plan,
    Playlist,
    ReviewComment,
    Track,
    User,
)
from app.infrastructure.repositories import (
    SCHEMA_PATH,
    SQLiteJamRepository,
    SQLitePlanRepository,
    SQLitePlaylistRepository,
    SQLiteReviewRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
)


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.commit()
    yield connection
    connection.close()


def test_track_deduplication_by_spotify_id(conn: sqlite3.Connection) -> None:
    track_repo = SQLiteTrackRepository(conn)

    initial_track = Track(
        title="Original Title",
        artist="Original Artist",
        duration_seconds=200,
        genre="Rock",
        spotify_id="spotify-unique-123",
        album="Album 1",
    )
    saved = track_repo.save(initial_track)
    assert saved.track_id is not None
    original_id = saved.track_id

    # Attempt to insert a second track without track_id but same spotify_id
    duplicate_candidate = Track(
        title="Updated Title",
        artist="Original Artist",
        duration_seconds=210,
        genre="Rock",
        spotify_id="spotify-unique-123",
        album="Album Remastered",
    )
    deduped = track_repo.save(duplicate_candidate)

    # It must update existing record and retain original track_id
    assert deduped.track_id == original_id
    assert deduped.title == "Updated Title"
    assert deduped.album == "Album Remastered"

    # Confirm there is only 1 track in the table
    all_tracks = track_repo.find_by_filters()
    assert len(all_tracks) == 1

    # find_by_spotify_id
    found = track_repo.find_by_spotify_id("spotify-unique-123")
    assert found is not None
    assert found.track_id == original_id
    assert track_repo.find_by_spotify_id("non-existent") is None


def test_track_list_blocked(conn: sqlite3.Connection) -> None:
    track_repo = SQLiteTrackRepository(conn)

    active_track = track_repo.save(
        Track(title="Active Song", artist="Artist", duration_seconds=180, genre="Pop")
    )
    blocked_track = track_repo.save(
        Track(
            title="Blocked Song",
            artist="Artist",
            duration_seconds=180,
            genre="Pop",
            is_deleted=True,
        )
    )

    blocked_list = track_repo.list_blocked()
    assert len(blocked_list) == 1
    assert blocked_list[0].track_id == blocked_track.track_id

    active_list = track_repo.list_active(limit=10)
    assert len(active_list) == 1
    assert active_list[0].track_id == active_track.track_id


def test_user_repository_birth_date(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)

    plan = plan_repo.save(Plan(name="FreePlan", initial_monthly_price=0.0))
    user = User(
        email="birthdate@example.com",
        password_hash="pw",
        display_name="Birth User",
        age=24,
        plan_id=plan.plan_id,
        birth_date="2002-05-20",
    )
    saved_user = user_repo.save(user)
    assert saved_user.user_id is not None
    assert saved_user.birth_date == "2002-05-20"

    retrieved = user_repo.find_by_id(saved_user.user_id)
    assert retrieved is not None
    assert retrieved.birth_date == "2002-05-20"

    # Update birth_date
    retrieved.birth_date = "2000-01-01"
    updated = user_repo.save(retrieved)
    assert updated.birth_date == "2000-01-01"


def test_playlist_repository_max_duration_and_deck_filters(
    conn: sqlite3.Connection,
) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)

    plan = plan_repo.save(Plan(name="PPlan", initial_monthly_price=0.0))
    user = user_repo.save(
        User(
            email="pl@example.com",
            password_hash="pw",
            display_name="PL",
            age=20,
            plan_id=plan.plan_id,
        )
    )
    track1 = track_repo.save(
        Track(title="T1", artist="A1", duration_seconds=100, genre="Pop")
    )
    track2 = track_repo.save(
        Track(title="T2", artist="A2", duration_seconds=120, genre="Pop")
    )

    playlist = Playlist(
        user_id=user.user_id,
        name="Deck Playlist",
        max_duration_seconds=3600,
        deck_filters='{"genre": "pop"}',
        initial_tracks=[track1, track2],
    )
    saved = playlist_repo.save(playlist)
    assert saved.playlist_id is not None
    assert saved.max_duration_seconds == 3600
    assert saved.deck_filters == '{"genre": "pop"}'
    assert len(saved.tracks) == 2

    # Remove track
    assert playlist_repo.remove_track(saved.playlist_id, track1.track_id) is True
    reloaded = playlist_repo.find_by_id(saved.playlist_id)
    assert reloaded is not None
    assert len(reloaded.tracks) == 1
    assert reloaded.tracks[0].track_id == track2.track_id

    # Delete playlist
    assert playlist_repo.delete(saved.playlist_id) is True
    assert playlist_repo.find_by_id(saved.playlist_id) is None


def test_jam_repository_columns_and_participants(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    jam_repo = SQLiteJamRepository(conn)
    track_repo = SQLiteTrackRepository(conn)

    plan = plan_repo.save(Plan(name="JamPlan", initial_monthly_price=0.0))
    host = user_repo.save(
        User(
            email="jamhost@example.com",
            password_hash="pw",
            display_name="Host",
            age=25,
            plan_id=plan.plan_id,
        )
    )
    participant = user_repo.save(
        User(
            email="guest@example.com",
            password_hash="pw",
            display_name="Guest",
            age=22,
            plan_id=plan.plan_id,
        )
    )
    track = track_repo.save(
        Track(title="Jam Song", artist="Artist", duration_seconds=200, genre="Rock")
    )

    jam = Jam.create(
        host_user_id=host.user_id,
        room_name="Party Room",
        duration_minutes=90,
        max_superlikes=15,
        skip_votes_threshold=4,
        deck_source="curtidas",
    )
    saved_jam = jam_repo.save(jam)
    assert saved_jam.jam_id is not None
    assert saved_jam.duration_minutes == 90
    assert saved_jam.max_superlikes == 15
    assert saved_jam.skip_votes_threshold == 4
    assert saved_jam.deck_source == "curtidas"
    assert saved_jam.accumulated_duration_seconds == 0

    # Host is automatically recognized as participant
    assert jam_repo.is_participant(saved_jam.jam_id, host.user_id) is True
    assert jam_repo.is_participant(saved_jam.jam_id, participant.user_id) is False

    # Add guest participant
    assert jam_repo.add_participant(saved_jam.jam_id, participant.user_id) is True
    assert jam_repo.is_participant(saved_jam.jam_id, participant.user_id) is True
    # Idempotent addition
    assert jam_repo.add_participant(saved_jam.jam_id, participant.user_id) is False

    participants = jam_repo.list_participants(saved_jam.jam_id)
    assert participant.user_id in participants

    # Skip voting
    assert jam_repo.count_skip_votes(saved_jam.jam_id, track.track_id) == 0
    assert (
        jam_repo.record_skip_vote(saved_jam.jam_id, track.track_id, participant.user_id)
        is True
    )
    # Duplicate vote ignored
    assert (
        jam_repo.record_skip_vote(saved_jam.jam_id, track.track_id, participant.user_id)
        is False
    )
    assert jam_repo.count_skip_votes(saved_jam.jam_id, track.track_id) == 1

    # Record vote from host
    assert (
        jam_repo.record_skip_vote(saved_jam.jam_id, track.track_id, host.user_id)
        is True
    )
    assert jam_repo.count_skip_votes(saved_jam.jam_id, track.track_id) == 2

    # Clear skip votes
    jam_repo.clear_skip_votes(saved_jam.jam_id, track.track_id)
    assert jam_repo.count_skip_votes(saved_jam.jam_id, track.track_id) == 0


def test_review_repository_active_unique_and_soft_delete(
    conn: sqlite3.Connection,
) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    review_repo = SQLiteReviewRepository(conn)

    plan = plan_repo.save(Plan(name="ReviewPlan", initial_monthly_price=0.0))
    user = user_repo.save(
        User(
            email="rev@example.com",
            password_hash="pw",
            display_name="Reviewer",
            age=28,
            plan_id=plan.plan_id,
        )
    )
    track = track_repo.save(
        Track(title="Review Track", artist="Artist", duration_seconds=180, genre="Jazz")
    )

    review = ReviewComment(
        user_id=user.user_id,
        track_id=track.track_id,
        initial_rating=4,
        text="Great jazz track",
    )
    saved = review_repo.save(review)
    assert saved.review_id is not None

    active = review_repo.find_active_by_user_and_track(user.user_id, track.track_id)
    assert active is not None
    assert active.review_id == saved.review_id

    # Soft delete
    assert review_repo.delete(saved.review_id) is True
    reloaded = review_repo.find_by_id(saved.review_id)
    assert reloaded is not None
    assert reloaded.is_deleted is True

    # No longer returned as active
    assert (
        review_repo.find_active_by_user_and_track(user.user_id, track.track_id) is None
    )

    # Idempotent review liking
    assert review_repo.has_user_liked(saved.review_id, user.user_id) is False
    review_repo.record_like(saved.review_id, user.user_id)
    assert review_repo.has_user_liked(saved.review_id, user.user_id) is True
    # Second call should not fail
    review_repo.record_like(saved.review_id, user.user_id)
    assert review_repo.has_user_liked(saved.review_id, user.user_id) is True
