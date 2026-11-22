"""Integration tests for track access tracking, seen IDs, and soft-delete isolation."""

lazy from pathlib import Path

from app.composition import create_app
from app.config import Settings
from app.infrastructure.repositories.connection import transaction
from tests.integration.test_client import TestClient


def test_track_access_and_soft_delete_isolation(tmp_path: Path) -> None:
    """Listeners never see soft-deleted tracks while admin access logs preserve them."""
    db_path = tmp_path / "track_access_flow.db"
    settings = Settings(
        database_path=str(db_path),
        password_hash_iterations=1_000,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    container = app.state.container

    # Seed two active tracks
    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Track Active', 'Artist 1', 200, 'Pop', 0, 0, '2026-01-01T00:00:00+00:00')
            """
        )
        active_id = int(cur.lastrowid or 0)
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Track Soon Deleted', 'Artist 2', 190, 'Rock', 0, 0, '2026-01-01T00:00:00+00:00')
            """
        )
        deleted_id = int(cur.lastrowid or 0)

    # Register listener
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": "listener@example.com",
            "password": "password123",
            "display_name": "Listener",
            "age": 24,
        },
    )
    assert reg_res.status_code == 201
    listener_token = reg_res.json()["access_token"]
    listener_id = reg_res.json()["user"]["user_id"]
    listener_headers = {"Authorization": f"Bearer {listener_token}"}

    # Record accesses to both tracks
    res1 = client.post(
        f"/api/tracks/{active_id}/access",
        json={"source": "play"},
        headers=listener_headers,
    )
    assert res1.status_code == 201
    assert res1.json()["source"] == "play"

    res2 = client.post(
        f"/api/tracks/{deleted_id}/access",
        json={"source": "details"},
        headers=listener_headers,
    )
    assert res2.status_code == 201

    # Also record a swipe interaction on the soon-to-be-deleted track
    swipe_res = client.post(
        "/api/discovery/interact",
        json={"track_id": deleted_id, "action": "like"},
        headers=listener_headers,
    )
    assert swipe_res.status_code == 200

    # Login as seeded admin
    admin_res = client.post(
        "/api/admin/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert admin_res.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

    # Soft-delete the second track via admin block endpoint
    block_res = client.put(
        f"/api/admin/tracks/{deleted_id}/block",
        json={"blocked": True},
        headers=admin_headers,
    )
    assert block_res.status_code == 200

    # Listener access history & seen IDs exclude the soft-deleted track
    hist_res = client.get("/api/profile/access-history", headers=listener_headers)
    assert hist_res.status_code == 200
    hist_body = hist_res.json()
    assert [item["track_id"] for item in hist_body["items"]] == [active_id]
    assert hist_body["seen_track_ids"] == [active_id]

    # Listener profile recent_interactions excludes the soft-deleted track
    prof_res = client.get("/api/profile/me", headers=listener_headers)
    assert prof_res.status_code == 200
    assert prof_res.json()["recent_interactions"] == []

    # Non-admin cannot access /api/admin/access-history
    forbidden_res = client.get("/api/admin/access-history", headers=listener_headers)
    assert forbidden_res.status_code == 403

    # Admin access history preserves the soft-deleted track with track_is_deleted=True
    admin_hist_res = client.get(
        f"/api/admin/access-history?user_id={listener_id}",
        headers=admin_headers,
    )
    assert admin_hist_res.status_code == 200
    entries = admin_hist_res.json()
    deleted_entries = [e for e in entries if e["track_id"] == deleted_id]
    assert len(deleted_entries) >= 1
    assert all(e["track_is_deleted"] is True for e in deleted_entries)

    only_del_res = client.get(
        "/api/admin/access-history?only_deleted=true",
        headers=admin_headers,
    )
    assert only_del_res.status_code == 200
    assert all(e["track_is_deleted"] is True for e in only_del_res.json())
