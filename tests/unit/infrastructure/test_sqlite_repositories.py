"""Unit tests for SQLite repositories implementing domain/application ports."""

import sqlite3
lazy from collections.abc import Iterator

import pytest

from app.domain.exceptions import EntityNotFoundError
from app.domain.models import (
    Interaction,
    InteractionAction,
    Jam,
    JamQueueItem,
    Plan,
    Playlist,
    ReviewComment,
    Track,
    User,
)
from app.infrastructure.repositories import (
    SCHEMA_PATH,
    SQLiteAuditLogRepository,
    SQLiteInteractionRepository,
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


def test_user_and_plan_repositories(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)

    plan = Plan(name="Family", initial_monthly_price=29.90, initial_max_profiles=6)
    saved_plan = plan_repo.save(plan)
    assert saved_plan.plan_id is not None
    assert plan_repo.find_by_id(saved_plan.plan_id) is not None
    assert plan_repo.find_by_name("Family") is not None

    user = User(
        email="john@example.com",
        password_hash="hashed_pw",
        display_name="John Doe",
        age=25,
        plan_id=saved_plan.plan_id,
        blocked_genres=frozenset({"metal"}),
    )
    saved_user = user_repo.save(user)
    assert saved_user.user_id is not None
    assert saved_user.blocked_genres == frozenset({"metal"})

    found_user = user_repo.find_by_email("JOHN@example.com")
    assert found_user is not None
    assert found_user.user_id == saved_user.user_id

    dependent = User(
        email="dep@example.com",
        password_hash="hashed_pw",
        display_name="Dep Doe",
        age=12,
        plan_id=saved_plan.plan_id,
        primary_account_id=saved_user.user_id,
    )
    saved_dep = user_repo.save(dependent)
    assert saved_dep.user_id is not None

    dependents = user_repo.list_dependents(saved_user.user_id)
    assert len(dependents) == 1
    assert dependents[0].email == "dep@example.com"

    assert len(user_repo.list_all()) == 2
    assert user_repo.delete(saved_dep.user_id) is True
    assert user_repo.find_by_id(saved_dep.user_id) is None


def test_track_and_interaction_repositories(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    interaction_repo = SQLiteInteractionRepository(conn)

    plan = plan_repo.save(
        Plan(name="Free", initial_monthly_price=0.0, initial_max_profiles=1)
    )
    user = user_repo.save(
        User(
            email="jane@example.com",
            password_hash="pw",
            display_name="Jane",
            age=20,
            plan_id=plan.plan_id,
        )
    )

    t1 = track_repo.save(
        Track(
            title="Bohemian Rhapsody",
            artist="Queen",
            duration_seconds=354,
            genre="Rock",
            explicit=False,
        )
    )
    _ = track_repo.save(
        Track(
            title="Rap God",
            artist="Eminem",
            duration_seconds=363,
            genre="Hip Hop",
            explicit=True,
        )
    )

    assert track_repo.count_all() == 2
    active_clean = track_repo.list_active(limit=10, block_explicit=True)
    assert len(active_clean) == 1
    assert active_clean[0].track_id == t1.track_id

    filtered = track_repo.find_by_filters(artist="queen")
    assert len(filtered) == 1
    assert filtered[0].title == "Bohemian Rhapsody"

    interaction = Interaction(
        user_id=user.user_id,
        track_id=t1.track_id,
        action=InteractionAction.LIKE,
    )
    saved_interaction = interaction_repo.save(interaction)
    assert saved_interaction.is_positive is True

    interacted_ids = interaction_repo.list_interacted_track_ids(user.user_id)
    assert interacted_ids == [t1.track_id]

    by_user = interaction_repo.list_by_user(user.user_id, action=InteractionAction.LIKE)
    assert len(by_user) == 1


def test_playlist_repository_aggregate(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)

    plan = plan_repo.save(Plan(name="Solo", initial_monthly_price=10.0))
    user = user_repo.save(
        User(
            email="bob@example.com",
            password_hash="pw",
            display_name="Bob",
            age=30,
            plan_id=plan.plan_id,
        )
    )
    track = track_repo.save(
        Track(
            title="Song A",
            artist="Artist A",
            duration_seconds=200,
            genre="Pop",
        )
    )

    playlist = Playlist(
        user_id=user.user_id,
        name="Favorites",
        description="My best tracks",
        initial_tracks=[track],
    )
    saved_playlist = playlist_repo.save(playlist)
    assert saved_playlist.playlist_id is not None
    assert len(saved_playlist.tracks) == 1
    assert saved_playlist.tracks[0].track_id == track.track_id

    loaded = playlist_repo.find_by_id(saved_playlist.playlist_id)
    assert loaded is not None
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].title == "Song A"

    user_playlists = playlist_repo.list_by_user(user.user_id)
    assert len(user_playlists) == 1
    assert len(user_playlists[0].tracks) == 1


def test_jam_and_review_repositories(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    jam_repo = SQLiteJamRepository(conn)
    review_repo = SQLiteReviewRepository(conn)

    plan = plan_repo.save(Plan(name="PlanJam", initial_monthly_price=0.0))
    user = user_repo.save(
        User(
            email="host@example.com",
            password_hash="pw",
            display_name="Host",
            age=22,
            plan_id=plan.plan_id,
        )
    )
    track = track_repo.save(
        Track(
            title="Track Jam",
            artist="Jammer",
            duration_seconds=180,
            genre="Indie",
        )
    )

    jam = Jam(host_user_id=user.user_id, room_name="Rock Party")
    saved_jam = jam_repo.save(jam)
    assert saved_jam.jam_id is not None
    assert jam_repo.find_by_code(saved_jam.room_code) is not None

    q_item = JamQueueItem(
        jam_id=saved_jam.jam_id,
        track_id=track.track_id,
        initial_vote_points=3,
    )
    saved_q = jam_repo.save_queue_item(q_item)
    assert saved_q.vote_points == 3

    queue = jam_repo.list_queue(saved_jam.jam_id)
    assert len(queue) == 1
    assert queue[0].track_id == track.track_id

    assert jam_repo.remove_track_from_queue(saved_jam.jam_id, track.track_id) is True
    assert len(jam_repo.list_queue(saved_jam.jam_id)) == 0

    review = ReviewComment(
        user_id=user.user_id,
        track_id=track.track_id,
        initial_rating=5,
        text="Masterpiece!",
        initial_likes_count=10,
    )
    saved_review = review_repo.save(review)
    assert saved_review.review_id is not None
    assert saved_review.rating == 5

    reviews_for_track = review_repo.list_by_track(track.track_id, limit=5)
    assert len(reviews_for_track) == 1
    assert reviews_for_track[0].text == "Masterpiece!"

    top_recent = review_repo.list_top_recent(days=7, limit=3)
    assert len(top_recent) == 1
    assert top_recent[0].likes_count == 10

    assert review_repo.has_user_liked(saved_review.review_id, user.user_id) is False
    review_repo.record_like(saved_review.review_id, user.user_id)
    assert review_repo.has_user_liked(saved_review.review_id, user.user_id) is True
    # Idempotency of record_like
    review_repo.record_like(saved_review.review_id, user.user_id)
    assert review_repo.has_user_liked(saved_review.review_id, user.user_id) is True


def test_interaction_repository_atomic_upsert(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    interaction_repo = SQLiteInteractionRepository(conn)

    plan = plan_repo.save(Plan(name="FreePlan", initial_monthly_price=0.0))
    user = user_repo.save(
        User(
            email="upsert@test.com",
            password_hash="pw",
            display_name="Upsert",
            age=20,
            plan_id=plan.plan_id,
        )
    )
    track = track_repo.save(
        Track(title="Song", artist="Art", duration_seconds=120, genre="Pop")
    )

    i1 = interaction_repo.save(
        Interaction(
            user_id=user.user_id,
            track_id=track.track_id,
            action=InteractionAction.LIKE,
        )
    )
    assert i1.action == InteractionAction.LIKE
    assert i1.interaction_id is not None

    i2 = interaction_repo.save(
        Interaction(
            user_id=user.user_id,
            track_id=track.track_id,
            action=InteractionAction.DISLIKE,
        )
    )
    assert i2.interaction_id == i1.interaction_id
    assert i2.action == InteractionAction.DISLIKE

    cursor = conn.execute(
        "SELECT * FROM interactions WHERE user_id = ? AND track_id = ?",
        (user.user_id, track.track_id),
    )
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == InteractionAction.DISLIKE.value


def test_repositories_raise_entity_not_found_on_missing_id(
    conn: sqlite3.Connection,
) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    jam_repo = SQLiteJamRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)
    review_repo = SQLiteReviewRepository(conn)

    with pytest.raises(EntityNotFoundError) as exc_info:
        plan_repo.save(Plan(plan_id=9999, name="Missing", initial_monthly_price=5.0))
    assert exc_info.value.details.get("entity_name") == "Plan"

    with pytest.raises(EntityNotFoundError) as exc_info:
        user_repo.save(
            User(
                user_id=9999,
                email="missing@x.com",
                password_hash="pw",
                display_name="Miss",
                age=20,
                plan_id=1,
            )
        )
    assert exc_info.value.details.get("entity_name") == "User"

    with pytest.raises(EntityNotFoundError) as exc_info:
        track_repo.save(
            Track(
                track_id=9999,
                title="Missing",
                artist="Nobody",
                duration_seconds=100,
                genre="Pop",
            )
        )
    assert exc_info.value.details.get("entity_name") == "Track"

    with pytest.raises(EntityNotFoundError) as exc_info:
        jam_repo.save(Jam(jam_id=9999, host_user_id=1, room_name="Missing"))
    assert exc_info.value.details.get("entity_name") == "Jam"

    with pytest.raises(EntityNotFoundError) as exc_info:
        playlist_repo.save(Playlist(playlist_id=9999, user_id=1, name="Missing"))
    assert exc_info.value.details.get("entity_name") == "Playlist"

    with pytest.raises(EntityNotFoundError) as exc_info:
        review_repo.save(
            ReviewComment(
                review_id=9999,
                user_id=1,
                track_id=1,
                initial_rating=3,
                text="Missing",
            )
        )
    assert exc_info.value.details.get("entity_name") == "ReviewComment"


def test_jam_repository_advance_playback_atomic(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    jam_repo = SQLiteJamRepository(conn)

    plan = plan_repo.save(Plan(name="PlanJamAdv", initial_monthly_price=0.0))
    user = user_repo.save(
        User(
            email="hostadv@test.com",
            password_hash="pw",
            display_name="AdvHost",
            age=25,
            plan_id=plan.plan_id,
        )
    )
    track1 = track_repo.save(
        Track(title="T1", artist="A1", duration_seconds=100, genre="Pop")
    )
    track2 = track_repo.save(
        Track(title="T2", artist="A2", duration_seconds=150, genre="Pop")
    )

    jam = jam_repo.save(Jam(host_user_id=user.user_id, room_name="JamAdv"))
    jam_repo.save_queue_item(
        JamQueueItem(
            jam_id=jam.jam_id,
            track_id=track1.track_id,
            initial_vote_points=5,
        )
    )
    jam_repo.save_queue_item(
        JamQueueItem(
            jam_id=jam.jam_id,
            track_id=track2.track_id,
            initial_vote_points=2,
        )
    )

    updated_jam = jam_repo.advance_playback(
        jam_id=jam.jam_id,
        new_track_id=track1.track_id,
        removed_track_id=track1.track_id,
    )
    assert updated_jam.current_track_id == track1.track_id

    queue = jam_repo.list_queue(jam.jam_id)
    assert len(queue) == 1
    assert queue[0].track_id == track2.track_id

    with pytest.raises(EntityNotFoundError):
        jam_repo.advance_playback(
            jam_id=9999,
            new_track_id=track2.track_id,
            removed_track_id=track2.track_id,
        )


def test_track_repository_find_by_ids(conn: sqlite3.Connection) -> None:
    track_repo = SQLiteTrackRepository(conn)

    assert track_repo.find_by_ids([]) == {}

    t1 = track_repo.save(
        Track(title="Track 1", artist="Art 1", duration_seconds=100, genre="Rock")
    )
    t2 = track_repo.save(
        Track(title="Track 2", artist="Art 2", duration_seconds=200, genre="Jazz")
    )

    tracks_map = track_repo.find_by_ids([t1.track_id, t2.track_id, 9999, t1.track_id])
    assert len(tracks_map) == 2
    assert t1.track_id in tracks_map
    assert t2.track_id in tracks_map
    assert tracks_map[t1.track_id].title == "Track 1"
    assert tracks_map[t2.track_id].title == "Track 2"


def test_counts_in_user_and_track_repositories(conn: sqlite3.Connection) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)

    assert user_repo.count_all() == 0
    assert track_repo.count_all() == 0
    assert track_repo.count_active() == 0

    plan = plan_repo.save(Plan(name="CountPlan", initial_monthly_price=0.0))
    user_repo.save(
        User(
            email="u1@test.com",
            password_hash="pw",
            display_name="U1",
            age=20,
            plan_id=plan.plan_id,
        )
    )
    user_repo.save(
        User(
            email="u2@test.com",
            password_hash="pw",
            display_name="U2",
            age=25,
            plan_id=plan.plan_id,
        )
    )

    assert user_repo.count_all() == 2

    track_repo.save(
        Track(title="Active Track", artist="Art", duration_seconds=100, genre="Pop")
    )
    track_repo.save(
        Track(
            title="Deleted Track",
            artist="Art",
            duration_seconds=100,
            genre="Pop",
            is_deleted=True,
        )
    )

    assert track_repo.count_all() == 2
    assert track_repo.count_active() == 1


def test_audit_log_repository(conn: sqlite3.Connection) -> None:
    audit_repo = SQLiteAuditLogRepository(conn)
    assert audit_repo.list_all() == []

    audit_repo.log_event("EVENT_A", "SUCCESS")
    audit_repo.log_event("EVENT_B", "FAILED")

    logs = audit_repo.list_all()
    assert len(logs) == 2
    assert logs[0].event == "EVENT_A"
    assert logs[0].status == "SUCCESS"
    assert logs[1].event == "EVENT_B"
    assert logs[1].status == "FAILED"


def test_plan_and_user_repositories_update_and_edge_cases(
    conn: sqlite3.Connection,
) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)

    assert plan_repo.find_by_id(9999) is None
    assert plan_repo.find_by_name("NonExistent") is None
    assert plan_repo.list_all() == []

    p1 = plan_repo.save(
        Plan(name="Basic", initial_monthly_price=5.0, initial_max_profiles=1)
    )
    p2 = plan_repo.save(
        Plan(name="Premium", initial_monthly_price=15.0, initial_max_profiles=2)
    )

    updated_p1 = Plan(
        plan_id=p1.plan_id,
        name="Basic Plus",
        initial_monthly_price=7.5,
        initial_max_profiles=2,
    )
    saved_p1 = plan_repo.save(updated_p1)
    assert saved_p1.name == "Basic Plus"
    assert saved_p1.monthly_price == 7.5
    assert saved_p1.max_profiles == 2

    all_plans = plan_repo.list_all()
    assert len(all_plans) == 2
    assert all_plans[0].name == "Basic Plus"
    assert all_plans[1].plan_id == p2.plan_id

    assert user_repo.find_by_id(9999) is None
    assert user_repo.find_by_email("nobody@example.com") is None
    assert user_repo.delete(9999) is False

    user = user_repo.save(
        User(
            email="alice@example.com",
            password_hash="hash1",
            display_name="Alice",
            age=28,
            plan_id=p1.plan_id,
            blocked_genres=frozenset(),
            is_admin=False,
        )
    )
    assert user.user_id is not None

    updated_user = User(
        user_id=user.user_id,
        email="alice.new@example.com",
        password_hash="hash2",
        display_name="Alice Updated",
        age=29,
        plan_id=p2.plan_id,
        spotify_id="sp_alice_99",
        blocked_genres=frozenset({"country", "jazz"}),
        is_admin=True,
    )
    saved_updated_user = user_repo.save(updated_user)
    assert saved_updated_user.email == "alice.new@example.com"
    assert saved_updated_user.display_name == "Alice Updated"
    assert saved_updated_user.age == 29
    assert saved_updated_user.plan_id == p2.plan_id
    assert saved_updated_user.spotify_id == "sp_alice_99"
    assert saved_updated_user.blocked_genres == frozenset({"country", "jazz"})
    assert saved_updated_user.is_admin is True


def test_track_repository_update_and_comprehensive_filters(
    conn: sqlite3.Connection,
) -> None:
    track_repo = SQLiteTrackRepository(conn)

    assert track_repo.find_by_id(9999) is None

    t1 = track_repo.save(
        Track(
            title="Stairway to Heaven",
            artist="Led Zeppelin",
            album="Led Zeppelin IV",
            duration_seconds=482,
            genre="Rock",
            release_year=1971,
            explicit=False,
        )
    )
    t2 = track_repo.save(
        Track(
            title="HUMBLE.",
            artist="Kendrick Lamar",
            album="DAMN.",
            duration_seconds=177,
            genre="Hip Hop",
            release_year=2017,
            explicit=True,
        )
    )
    t3 = track_repo.save(
        Track(
            title="Deleted Song",
            artist="Led Zeppelin",
            album="Coda",
            duration_seconds=200,
            genre="Rock",
            release_year=1982,
            is_deleted=False,
        )
    )

    assert t1.track_id is not None
    assert t2.track_id is not None
    assert t3.track_id is not None

    # Update t3 to mark deleted and change metadata
    t3_updated = Track(
        track_id=t3.track_id,
        title="Deleted Song Updated",
        artist="Led Zeppelin",
        album="Coda Deluxe",
        duration_seconds=210,
        genre="Rock",
        release_year=1982,
        spotify_id="sp_t3",
        explicit=True,
        is_deleted=True,
    )
    saved_t3 = track_repo.save(t3_updated)
    assert saved_t3.is_deleted is True
    assert saved_t3.title == "Deleted Song Updated"
    assert saved_t3.spotify_id == "sp_t3"

    # list_active with excluded_ids and excluded_genres
    active_filtered = track_repo.list_active(
        limit=10,
        excluded_genres=["Hip Hop", "  "],
        excluded_ids=[9999],
    )
    assert len(active_filtered) == 1
    assert active_filtered[0].track_id == t1.track_id

    active_excluding_t1 = track_repo.list_active(
        limit=10,
        excluded_ids=[t1.track_id],
    )
    assert len(active_excluding_t1) == 1
    assert active_excluding_t1[0].track_id == t2.track_id

    # find_by_filters: query, artist, album, genre, year, pagination, and deleted exclusion
    assert len(track_repo.find_by_filters()) == 2
    assert len(track_repo.find_by_filters(query="heaven")) == 1
    assert len(track_repo.find_by_filters(query="damn")) == 1
    assert len(track_repo.find_by_filters(album="zeppelin iv")) == 1
    assert len(track_repo.find_by_filters(genre="rock")) == 1
    assert len(track_repo.find_by_filters(year=2017)) == 1
    assert len(track_repo.find_by_filters(year=1982)) == 0  # t3 is deleted
    assert len(track_repo.find_by_filters(limit=1, offset=1)) == 1


def test_playlist_jam_review_interaction_updates_and_missing_cases(
    conn: sqlite3.Connection,
) -> None:
    plan_repo = SQLitePlanRepository(conn)
    user_repo = SQLiteUserRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)
    jam_repo = SQLiteJamRepository(conn)
    review_repo = SQLiteReviewRepository(conn)
    interaction_repo = SQLiteInteractionRepository(conn)

    plan = plan_repo.save(Plan(name="AllInOne", initial_monthly_price=10.0))
    user = user_repo.save(
        User(
            email="tester@example.com",
            password_hash="pw",
            display_name="Tester",
            age=24,
            plan_id=plan.plan_id,
        )
    )
    t1 = track_repo.save(
        Track(title="T1", artist="A1", duration_seconds=180, genre="Pop")
    )
    t2 = track_repo.save(
        Track(title="T2", artist="A2", duration_seconds=200, genre="Rock")
    )
    assert user.user_id is not None
    assert t1.track_id is not None
    assert t2.track_id is not None

    # Playlist missing & update replacing tracks
    assert playlist_repo.find_by_id(9999) is None
    pl = playlist_repo.save(
        Playlist(
            user_id=user.user_id,
            name="Initial PL",
            description="Desc 1",
            initial_tracks=[t1],
        )
    )
    assert pl.playlist_id is not None
    updated_pl = playlist_repo.save(
        Playlist(
            playlist_id=pl.playlist_id,
            user_id=user.user_id,
            name="Updated PL",
            description="Desc 2",
            spotify_playlist_id="spotify:playlist:abc",
            is_exported=True,
            initial_tracks=[t2],
        )
    )
    assert updated_pl.name == "Updated PL"
    assert updated_pl.is_exported is True
    assert len(updated_pl.tracks) == 1
    assert updated_pl.tracks[0].track_id == t2.track_id

    # Jam missing, update, queue upsert, and remove missing
    assert jam_repo.find_by_id(9999) is None
    assert jam_repo.find_by_code("MISSINGCODE") is None
    assert jam_repo.find_queue_item(9999, 9999) is None
    assert jam_repo.remove_track_from_queue(9999, 9999) is False

    jam = jam_repo.save(Jam(host_user_id=user.user_id, room_name="Room 1"))
    assert jam.jam_id is not None

    q1 = jam_repo.save_queue_item(
        JamQueueItem(jam_id=jam.jam_id, track_id=t1.track_id, initial_vote_points=1)
    )
    assert q1.vote_points == 1

    # Upsert existing queue item updates vote_points
    q1_updated = jam_repo.save_queue_item(
        JamQueueItem(jam_id=jam.jam_id, track_id=t1.track_id, initial_vote_points=7)
    )
    assert q1_updated.vote_points == 7

    # Update Jam state (e.g. closing jam)
    jam_closed = jam_repo.save(
        Jam(
            jam_id=jam.jam_id,
            host_user_id=user.user_id,
            room_name="Room 1 Closed",
            room_code=jam.room_code,
            is_active=False,
            current_track_id=t1.track_id,
        )
    )
    assert jam_closed.is_active is False
    assert jam_closed.current_track_id == t1.track_id
    # Inactive jam should not be returned by find_by_code
    assert jam_repo.find_by_code(jam.room_code) is None

    # Review missing & update existing review
    assert review_repo.find_by_id(9999) is None
    rev = review_repo.save(
        ReviewComment(
            user_id=user.user_id,
            track_id=t1.track_id,
            initial_rating=4,
            text="Good track",
            initial_likes_count=0,
        )
    )
    assert rev.review_id is not None
    rev_updated = review_repo.save(
        ReviewComment(
            review_id=rev.review_id,
            user_id=user.user_id,
            track_id=t1.track_id,
            initial_rating=5,
            text="Great track!",
            initial_likes_count=3,
            is_deleted=True,
        )
    )
    assert rev_updated.rating == 5
    assert rev_updated.likes_count == 3
    assert rev_updated.is_deleted is True
    # Deleted review excluded from list_by_track and list_top_recent
    assert review_repo.list_by_track(t1.track_id, limit=10) == []
    assert review_repo.list_top_recent(days=7, limit=10) == []

    # Interaction find_by_user_and_track and list_by_user with and without action filter
    assert interaction_repo.find_by_user_and_track(user.user_id, 9999) is None
    interaction_repo.save(
        Interaction(
            user_id=user.user_id, track_id=t1.track_id, action=InteractionAction.LIKE
        )
    )
    interaction_repo.save(
        Interaction(
            user_id=user.user_id, track_id=t2.track_id, action=InteractionAction.DISLIKE
        )
    )
    all_user_interactions = interaction_repo.list_by_user(user.user_id)
    assert len(all_user_interactions) == 2
    dislike_interactions = interaction_repo.list_by_user(
        user.user_id, action=InteractionAction.DISLIKE
    )
    assert len(dislike_interactions) == 1
    assert dislike_interactions[0].track_id == t2.track_id
