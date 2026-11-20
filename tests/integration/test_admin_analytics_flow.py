"""Integration tests for admin financial costs and audience access analytics."""

lazy from pathlib import Path

from app.composition import create_app
from app.config import Settings
from app.infrastructure.repositories.connection import transaction
from tests.integration.test_client import TestClient


def test_admin_costs_dashboard_and_audience_access_analytics(tmp_path: Path) -> None:
    """Admin can read/update platform costs and inspect access analytics on dashboard/audience."""
    db_path = tmp_path / "admin_analytics.db"
    settings = Settings(
        database_path=str(db_path),
        password_hash_iterations=1_000,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    container = app.state.container

    with transaction(container.connection) as cur:
        cur.execute(
            """
            INSERT INTO tracks (title, artist, duration_seconds, genre, explicit, is_deleted, created_at)
            VALUES ('Analytics Track', 'Analytics Artist', 210, 'Indie', 0, 0, '2026-01-01T00:00:00+00:00')
            """
        )
        track_id = int(cur.lastrowid or 0)

    # Listener registers and accesses track
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": "listener2@example.com",
            "password": "password123",
            "display_name": "Listener 2",
            "age": 25,
        },
    )
    assert reg_res.status_code == 201
    listener_headers = {"Authorization": f"Bearer {reg_res.json()['access_token']}"}

    assert (
        client.post(
            f"/api/tracks/{track_id}/access",
            json={"source": "play"},
            headers=listener_headers,
        ).status_code
        == 201
    )

    # Non-admin blocked from /api/admin/costs
    assert client.get("/api/admin/costs", headers=listener_headers).status_code == 403

    # Admin login
    admin_res = client.post(
        "/api/admin/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert admin_res.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

    # GET /api/admin/costs
    costs_res = client.get("/api/admin/costs", headers=admin_headers)
    assert costs_res.status_code == 200
    assert costs_res.json()["content_cost_per_track"] == 0.04

    # Reject negative cost
    bad_res = client.put(
        "/api/admin/costs",
        json={
            "content_cost_per_track": -1.0,
            "infrastructure_fixed_cost": 10.0,
            "infrastructure_cost_per_user": 0.5,
        },
        headers=admin_headers,
    )
    assert bad_res.status_code == 422

    # PUT /api/admin/costs with high fixed cost to verify negative net revenue
    upd_res = client.put(
        "/api/admin/costs",
        json={
            "content_cost_per_track": 1.0,
            "infrastructure_fixed_cost": 100.0,
            "infrastructure_cost_per_user": 2.0,
        },
        headers=admin_headers,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["infrastructure_fixed_cost"] == 100.0

    dash_res = client.get("/api/admin/dashboard", headers=admin_headers)
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert dash["gross_revenue"] == 0.0
    assert dash["total_costs"] > 100.0
    assert dash["estimated_net_revenue"] < 0.0

    aud_res = client.get("/api/admin/audience", headers=admin_headers)
    assert aud_res.status_code == 200
    aud = aud_res.json()
    assert aud["total_accesses"] == 1
    assert aud["accesses_by_track"][0]["track_id"] == track_id
    assert aud["accesses_by_genre"][0]["genre"] == "Indie"
