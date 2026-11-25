"""Integration tests for parental controls, soft-delete isolation, and minor bypasses."""

lazy from pathlib import Path

from app.composition import create_app
from app.config import Settings
from app.domain.models.track import Track
from app.infrastructure.repositories.connection import transaction
from tests.integration.test_client import TestClient


def _make_client(tmp_path: Path, name: str) -> tuple[TestClient, object]:
    db_path = tmp_path / f"{name}.db"
    app = create_app(
        settings=Settings(database_path=str(db_path), password_hash_iterations=1_000)
    )
    return TestClient(app), app.state.container


def test_family_parental_controls_201_and_minor_bypasses_closed(tmp_path: Path) -> None:
    client, container = _make_client(tmp_path, "minor_and_parental")

    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Clean Pop', 'Safe Artist', 180, 'Pop', 0, 0, '2026-01-01T00:00:00+00:00')
            """
        )
        clean_id = int(cur.lastrowid or 0)
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Explicit Track', 'Explicit Artist', 200, 'Pop', 1, 0, '2026-01-01T00:00:00+00:00')
            """
        )
        explicit_id = int(cur.lastrowid or 0)
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Clean Pop 2', 'Safe Artist 2', 180, 'Pop', 0, 0, '2026-01-01T00:00:00+00:00')
            """
        )

    # Register Family plan parent (plan_id=3)
    parent_reg = client.post(
        "/api/auth/register",
        json={
            "email": "parent@example.com",
            "password": "Password123!",
            "display_name": "Parent",
            "age": 40,
            "plan_id": 3,
        },
    )
    assert parent_reg.status_code == 201
    parent_headers = {"Authorization": f"Bearer {parent_reg.json()['access_token']}"}

    # Provision minor dependent -> 201 Created
    dep_res = client.post(
        "/api/profile/family/members",
        headers=parent_headers,
        json={
            "email": "minor_child@example.com",
            "password": "Password123!",
            "display_name": "Minor Child",
            "birth_date": "2014-05-01",
        },
    )
    assert dep_res.status_code == 201
    minor_id = dep_res.json()["user_id"]

    # Parental controls PUT endpoint works without 404
    pc_res = client.put(
        f"/api/profile/family/members/{minor_id}/parental-controls",
        headers=parent_headers,
        json={"blocked_genres": ["Rock"], "blocked_artists": ["Banned Artist"]},
    )
    assert pc_res.status_code == 200
    assert "rock" in pc_res.json()["blocked_genres"]

    # Parent publishes reviews on both clean and explicit tracks
    assert (
        client.post(
            "/api/reviews",
            headers=parent_headers,
            json={"track_id": clean_id, "rating": 5, "text": "Nice"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/reviews",
            headers=parent_headers,
            json={"track_id": explicit_id, "rating": 4, "text": "Explicit review"},
        ).status_code
        == 201
    )

    # Anonymous feed still sees both
    anon_feed = client.get("/api/reviews/feed")
    assert anon_feed.status_code == 200
    assert {r["track_id"] for r in anon_feed.json()} == {clean_id, explicit_id}

    # Minor login
    minor_login = client.post(
        "/api/auth/login",
        json={"email": "minor_child@example.com", "password": "Password123!"},
    )
    assert minor_login.status_code == 200
    minor_headers = {"Authorization": f"Bearer {minor_login.json()['access_token']}"}

    # Minor feed & track reviews filter out explicit track
    minor_feed = client.get("/api/reviews/feed", headers=minor_headers)
    assert minor_feed.status_code == 200
    assert [r["track_id"] for r in minor_feed.json()] == [clean_id]

    minor_track_reviews = client.get(
        f"/api/reviews/track/{explicit_id}", headers=minor_headers
    )
    assert minor_track_reviews.status_code == 200
    assert minor_track_reviews.json() == []

    # Minor search pagination pushes minor filters into SQL before LIMIT
    search_res = client.get(
        "/api/tracks/search?query=Pop&limit=2", headers=minor_headers
    )
    assert search_res.status_code == 200
    returned_ids = [t["track_id"] for t in search_res.json()]
    assert explicit_id not in returned_ids
    assert len(returned_ids) == 2

    # Minor playlists filter out restricted tracks
    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO playlists (user_id, name, is_exported, created_at)
            VALUES (?, 'Minor Mix', 0, '2026-01-01T00:00:00+00:00')
            """,
            (minor_id,),
        )
        pl_id = int(cur.lastrowid or 0)
        cur.execute(
            "INSERT INTO playlist_tracks (playlist_id, track_id, added_at) VALUES (?, ?, '2026-01-01T00:00:00+00:00')",
            (pl_id, clean_id),
        )
        cur.execute(
            "INSERT INTO playlist_tracks (playlist_id, track_id, added_at) VALUES (?, ?, '2026-01-01T00:00:00+00:00')",
            (pl_id, explicit_id),
        )

    pl_list = client.get("/api/playlists", headers=minor_headers)
    assert pl_list.status_code == 200
    assert [t["track_id"] for t in pl_list.json()[0]["tracks"]] == [clean_id]

    pl_one = client.get(f"/api/playlists/{pl_id}", headers=minor_headers)
    assert pl_one.status_code == 200
    assert [t["track_id"] for t in pl_one.json()["tracks"]] == [clean_id]

    # Minor discovery undo hides restricted track payload
    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO interactions (user_id, track_id, action, created_at, source)
            VALUES (?, ?, 'like', '2026-01-02T00:00:00+00:00', 'discovery')
            """,
            (minor_id, explicit_id),
        )
    undo_res = client.post("/api/discovery/undo", headers=minor_headers)
    assert undo_res.status_code == 200
    assert undo_res.json()["track"] is None


def test_soft_delete_no_resurrection_and_user_stats_exclusion(tmp_path: Path) -> None:
    _, container = _make_client(tmp_path, "soft_delete_stats")

    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO tracks (spotify_id, title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('sp-1', 'Deleted Track', 'Artist', 180, 'Pop', 0, 1, '2026-01-01T00:00:00+00:00')
            """
        )
        deleted_id = int(cur.lastrowid or 0)
        cur.execute(
            """
            INSERT INTO users (email, password_hash, display_name, age, plan_id, created_at)
            VALUES ('u@example.com', 'hash', 'User', 25, 2, '2026-01-01T00:00:00+00:00')
            """
        )
        uid = int(cur.lastrowid or 0)
        cur.execute(
            """
            INSERT INTO interactions (user_id, track_id, action, created_at, source)
            VALUES (?, ?, 'like', '2026-02-01T00:00:00+00:00', 'discovery')
            """,
            (uid, deleted_id),
        )
        cur.execute(
            """
            INSERT INTO reviews (user_id, track_id, rating, text, is_deleted, created_at)
            VALUES (?, ?, 5, 'Should not count', 0, '2026-02-01T00:00:00+00:00')
            """,
            (uid, deleted_id),
        )

    # Upsert by spotify_id must NOT resurrect is_deleted=1
    saved = container.track_repo.save(
        Track(
            spotify_id="sp-1",
            title="Deleted Track Updated",
            artist="Artist",
            duration_seconds=180,
            genre="Pop",
            is_deleted=False,
        )
    )
    assert saved.is_deleted is True

    # UserStatsRepository excludes soft-deleted track from all aggregations
    stats = container.get_annual_listening_stats_use_case.execute(uid)
    assert stats.total_interactions == 0
    assert stats.by_interaction_year == []
    assert stats.by_month == []
    assert stats.by_source == []
    assert stats.total_reviews == 0
