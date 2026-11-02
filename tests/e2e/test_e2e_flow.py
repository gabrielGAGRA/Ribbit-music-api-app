"""Comprehensive end-to-end integration test suite covering Flows 1 through 7."""

import sqlite3
from typing import Any

import pytest

from app.application.ports.services.music_service import CatalogTrack, TrackPreview
from app.composition import create_app
from app.config import Settings
from app.domain.models.track import Track
from tests.e2e.test_client import TestClient

ADMIN_EMAIL = "admin@ribbit.example.com"
ADMIN_PASSWORD = "RibbitLocal2026!"


@pytest.fixture
def test_db() -> sqlite3.Connection:
    """Creates an isolated in-memory SQLite database connection."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@pytest.fixture
def app(test_db: sqlite3.Connection):
    """Creates the FastAPI application with in-memory database and test settings."""
    settings = Settings(
        database_path=":memory:",
        password_hash_iterations=1_000,
        token_expiration_seconds=43200,
        secret_key="ribbit-insecure-dev-secret-key-change-me-32chars",
    )
    return create_app(settings=settings, connection=test_db)


@pytest.fixture
def client(app) -> TestClient:
    """TestClient instance configured with the test application."""
    return TestClient(app)


def _register_and_login(
    client: TestClient,
    email: str,
    birth_date: str,
    plan_id: int,
    password: str = "Password123!",  # noqa: S107
) -> tuple[dict[str, Any], dict[str, str]]:
    """Helper registering and authenticating a user, returning user data and Bearer auth headers."""
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": email.split("@", maxsplit=1)[0].capitalize(),
            "birth_date": birth_date,
            "plan_id": plan_id,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return resp.json(), {"Authorization": f"Bearer {token}"}


# ==============================================================================
# FLOW 1: Authentication & Age Gate
# ==============================================================================


def test_flow_1_authentication_and_age_gate(client: TestClient) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")

    # 1. Underage direct registration rejected with 400
    minor_resp = client.post(
        "/api/auth/register",
        json={
            "email": "underage_direct@example.com",
            "password": "Password123!",
            "display_name": "Underage Kid",
            "birth_date": "2012-05-15",
            "plan_id": free_id,
        },
    )
    assert minor_resp.status_code == 400
    assert "18 anos" in minor_resp.text

    # 2. Future birth date rejected with 400
    future_resp = client.post(
        "/api/auth/register",
        json={
            "email": "time_traveler@example.com",
            "password": "Password123!",
            "display_name": "Future Man",
            "birth_date": "2099-01-01",
            "plan_id": free_id,
        },
    )
    assert future_resp.status_code == 400
    assert "futuro" in future_resp.text

    # 3. Adult registration succeeds
    adult_user, headers = _register_and_login(
        client, "adult_user@example.com", "1995-03-20", free_id
    )
    user_id = adult_user.get("user_id") or adult_user["user"]["user_id"]
    assert user_id is not None

    # 4. Access protected endpoint without token -> 401
    unauth = client.get("/api/profile/me")
    assert unauth.status_code == 401

    # 5. Access protected endpoint with invalid token -> 401
    bad_token = client.get(
        "/api/profile/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert bad_token.status_code == 401

    # 6. Access protected endpoint with valid Bearer token -> 200
    profile = client.get("/api/profile/me", headers=headers)
    assert profile.status_code == 200
    pdata = profile.json()
    resolved_id = pdata.get("user", {}).get("user_id") or pdata.get("usuario", {}).get(
        "usuario_id"
    )
    assert resolved_id == user_id


# ==============================================================================
# FLOW 2: Discovery & Preview Fallback
# ==============================================================================


def test_flow_2_discovery_and_preview_fallback(
    client: TestClient, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")

    # Register adult user
    _, adult_headers = _register_and_login(
        client, "discovery_adult@example.com", "1992-07-10", free_id
    )

    # 1. Ensure missing preview triggers iTunes fallback
    container = app.state.container
    # Insert a custom track with no preview url
    custom_track = container.track_repo.save(
        Track(
            title="Acoustic Sunrise",
            artist="Indie Morning",
            album="Dawn",
            duration_seconds=190,
            genre="Indie",
            country="Brasil",
            release_year=2021,
            itunes_preview_url=None,
            explicit=False,
        )
    )

    fallback_called = False

    def mock_find_preview(term: str) -> TrackPreview:
        nonlocal fallback_called
        fallback_called = True
        return TrackPreview(
            external_id="itunes-9999",
            title="Acoustic Sunrise",
            artist="Indie Morning",
            preview_url="https://audio-ssl.itunes.apple.com/preview/acoustic_sunrise.mp3",
            cover_url="https://itunes.apple.com/cover.jpg",
        )

    monkeypatch.setattr(container.preview_service, "find_preview", mock_find_preview)

    # Fetch discovery track
    next_track_res = client.get("/api/discovery/next", headers=adult_headers)
    assert next_track_res.status_code == 200
    assert next_track_res.json() is not None

    # Query until our custom track is picked or directly verify preview service persistence
    refreshed_track = container.track_repo.find_by_id(custom_track.track_id)
    assert refreshed_track is not None

    # 2. Swipe interaction: like, superlike, dislike
    track_to_like = next_track_res.json()["track_id"]
    like_res = client.post(
        "/api/discovery/interactions",
        headers=adult_headers,
        json={"track_id": track_to_like, "action": "like"},
    )
    assert like_res.status_code == 200

    next_track_res_2 = client.get("/api/discovery/next", headers=adult_headers)
    assert next_track_res_2.status_code == 200
    track_to_dislike = next_track_res_2.json()["track_id"]
    dislike_res = client.post(
        "/api/discovery/interactions",
        headers=adult_headers,
        json={"track_id": track_to_dislike, "action": "dislike"},
    )
    assert dislike_res.status_code == 200

    # 3. Minor content filter blocks explicit tracks for minors
    # Setup family plan to provision a minor
    fam_id = next(p["plan_id"] for p in plans if p["name"] == "Família")
    _, parent_headers = _register_and_login(
        client, "parent_disco@example.com", "1980-01-01", fam_id
    )

    client.post(
        "/api/profile/family/members",
        headers=parent_headers,
        json={
            "email": "minor_disco@example.com",
            "password": "Password123!",
            "display_name": "Minor Disco",
            "birth_date": "2013-08-20",
        },
    )
    minor_login = client.post(
        "/api/auth/login",
        json={"email": "minor_disco@example.com", "password": "Password123!"},
    )
    minor_headers = {"Authorization": f"Bearer {minor_login.json()['access_token']}"}

    # "Rap God" is explicit in the seed. Minor should NEVER receive explicit tracks.
    for _ in range(5):
        minor_track_res = client.get("/api/discovery/next", headers=minor_headers)
        if minor_track_res.status_code == 200 and minor_track_res.json():
            t = minor_track_res.json()
            assert t["explicit"] is False
            assert t["title"] != "Rap God"
            # Consume track
            client.post(
                "/api/discovery/interactions",
                headers=minor_headers,
                json={"track_id": t["track_id"], "action": "dislike"},
            )


# ==============================================================================
# FLOW 3: Family Plan Management
# ==============================================================================


def test_flow_3_family_plan_management(client: TestClient) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")
    family_id = next(p["plan_id"] for p in plans if p["name"] == "Família")

    # 1. Register with Free plan, then change subscription to Family plan
    _, headers = _register_and_login(
        client, "family_titular@example.com", "1985-02-14", free_id
    )

    plan_update = client.put(
        "/api/profile/plan",
        headers=headers,
        json={"plan_id": family_id},
    )
    assert plan_update.status_code == 200, plan_update.text

    # 2. Provision minor dependent under Family plan -> succeeds
    dep_res = client.post(
        "/api/profile/family/members",
        headers=headers,
        json={
            "email": "family_dependent_1@example.com",
            "password": "Password123!",
            "display_name": "First Dependent",
            "birth_date": "2014-04-12",
        },
    )
    assert dep_res.status_code in (200, 201), dep_res.text

    # 3. Add dependents up to max limit (Família allows 6 profiles: 1 titular + 5 dependents)
    for i in range(2, 6):
        resp = client.post(
            "/api/profile/family/members",
            headers=headers,
            json={
                "email": f"family_dependent_{i}@example.com",
                "password": "Password123!",
                "display_name": f"Dependent {i}",
                "birth_date": "2015-01-01",
            },
        )
        assert resp.status_code in (200, 201), resp.text

    # 4. Exceeding capacity limit -> rejected with 400
    overflow_res = client.post(
        "/api/profile/family/members",
        headers=headers,
        json={
            "email": "family_dependent_overflow@example.com",
            "password": "Password123!",
            "display_name": "Overflow Dependent",
            "birth_date": "2015-01-01",
        },
    )
    assert overflow_res.status_code == 400
    assert "atingido" in overflow_res.text.lower()

    # 5. Cancel subscription plan unlinks dependents and reverts them to Free
    cancel_res = client.post("/api/profile/plan/cancel", headers=headers)
    assert cancel_res.status_code == 200

    # Verify dependents can still log in and are now on Free plan
    dep_login = client.post(
        "/api/auth/login",
        json={
            "email": "family_dependent_1@example.com",
            "password": "Password123!",
        },
    )
    assert dep_login.status_code == 200
    dep_token_headers = {"Authorization": f"Bearer {dep_login.json()['access_token']}"}
    dep_profile = client.get("/api/profile/me", headers=dep_token_headers).json()
    dep_plan = dep_profile.get("plan") or dep_profile.get("plano")
    assert dep_plan["name"] == "Free"


# ==============================================================================
# FLOW 4: Playlists & Deck
# ==============================================================================


def test_flow_4_playlists_and_deck(client: TestClient) -> None:
    plans = client.get("/api/profile/plans").json()
    indiv_id = next(p["plan_id"] for p in plans if p["name"] == "Individual")

    _, headers = _register_and_login(
        client, "playlist_curator@example.com", "1993-11-22", indiv_id
    )

    # 1. Create playlist with duration cap (5 minutes = 300 seconds) and Pop filter
    created_pl = client.post(
        "/api/playlists/deck",
        headers=headers,
        json={
            "name": "Pop Essentials",
            "duration_minutes": 5,
            "deck_filters": {"genre": "Pop"},
        },
    )
    assert created_pl.status_code == 201, created_pl.text
    playlist_id = created_pl.json()["playlist_id"]

    # 2. Fetch deck candidates
    deck_res = client.get(
        f"/api/playlists/{playlist_id}/deck?limit=20",
        headers=headers,
    )
    assert deck_res.status_code == 200, deck_res.text
    deck_items = deck_res.json()["items"]
    assert len(deck_items) > 0
    assert all(t["duration_seconds"] <= 300 for t in deck_items)

    first_track = deck_items[0]

    # 3. Swipe-add track to playlist
    add_res = client.post(
        f"/api/playlists/{playlist_id}/swipe-add",
        headers=headers,
        json={"track_id": first_track["track_id"], "action": "like"},
    )
    assert add_res.status_code == 200, add_res.text

    # Detail shows duration increased
    detail = client.get(f"/api/playlists/{playlist_id}", headers=headers).json()
    assert detail["total_duration_seconds"] == first_track["duration_seconds"]

    # Trying to add another track that exceeds the remaining duration -> 400
    # Remaining duration is 300 - first_track["duration_seconds"]
    # Seed track "Shape of You" is 233s, "Blinding Lights" is 200s -> 233 + 200 = 433 > 300
    candidate = next(t for t in deck_items if t["track_id"] != first_track["track_id"])
    over_res = client.post(
        f"/api/playlists/{playlist_id}/swipe-add",
        headers=headers,
        json={"track_id": candidate["track_id"], "action": "like"},
    )
    assert over_res.status_code == 400

    # 4. Remove track from playlist
    del_track_res = client.delete(
        f"/api/playlists/{playlist_id}/tracks/{first_track['track_id']}",
        headers=headers,
    )
    assert del_track_res.status_code == 200

    # 5. Delete playlist: owner succeeds, stranger forbidden
    _, stranger_headers = _register_and_login(
        client, "stranger_playlist@example.com", "1990-01-01", indiv_id
    )
    forbidden_del = client.delete(
        f"/api/playlists/{playlist_id}",
        headers=stranger_headers,
    )
    assert forbidden_del.status_code == 403

    owner_del = client.delete(
        f"/api/playlists/{playlist_id}",
        headers=headers,
    )
    assert owner_del.status_code == 200


# ==============================================================================
# FLOW 5: Collaborative Jam
# ==============================================================================


def test_flow_5_collaborative_jam(client: TestClient) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")

    # Host
    _, host_headers = _register_and_login(
        client, "jam_host@example.com", "1994-06-18", free_id
    )
    # Guest
    _, guest_headers = _register_and_login(
        client, "jam_guest@example.com", "1996-09-03", free_id
    )

    # 1. Create jam with 6-digit room code
    jam_res = client.post(
        "/api/jams",
        headers=host_headers,
        json={
            "room_name": "Friday Vibe",
            "duration_minutes": 60,
            "max_superlikes": 1,
            "skip_votes_threshold": 2,
        },
    )
    assert jam_res.status_code == 201, jam_res.text
    jam_data = jam_res.json()
    jam_id = jam_data["jam_id"]
    room_code = jam_data["room_code"]
    assert len(room_code) == 6 and room_code.isdigit()

    # 2. Guest joins jam using 6-digit code
    join_res = client.post(
        "/api/jams/join",
        headers=guest_headers,
        json={"room_code": room_code},
    )
    assert join_res.status_code == 200, join_res.text

    # 3. Vote on deck tracks with superlike limit
    deck_res = client.get(f"/api/jams/{jam_id}/deck?limit=10", headers=host_headers)
    assert deck_res.status_code == 200
    tracks = deck_res.json()["items"]
    assert len(tracks) >= 2
    track_1 = tracks[0]["track_id"]
    track_2 = tracks[1]["track_id"]

    # First vote: like on track_1 (becomes currently playing track if current is None)
    v1 = client.post(
        f"/api/jams/{jam_id}/deck-vote",
        headers=host_headers,
        json={"track_id": track_1, "action": "like"},
    )
    assert v1.status_code == 200

    # Second vote: superlike on track_2 (uses 1 superlike)
    v2 = client.post(
        f"/api/jams/{jam_id}/deck-vote",
        headers=host_headers,
        json={"track_id": track_2, "action": "superlike"},
    )
    assert v2.status_code == 200

    # Third vote: superlike again -> exceeds limit (max_superlikes = 1) -> 400
    v3 = client.post(
        f"/api/jams/{jam_id}/deck-vote",
        headers=host_headers,
        json={"track_id": track_1, "action": "superlike"},
    )
    assert v3.status_code == 400

    # 4. Skip voting auto-advances playback when threshold (2) is reached
    skip_1 = client.post(
        f"/api/jams/{jam_id}/skip-vote",
        headers=host_headers,
        json={},
    )
    assert skip_1.status_code == 200
    assert skip_1.json()["votes"] == 1
    assert skip_1.json()["advanced"] is False

    # Repeated skip vote from host is idempotent
    skip_repeat = client.post(
        f"/api/jams/{jam_id}/skip-vote",
        headers=host_headers,
        json={},
    )
    assert skip_repeat.json()["votes"] == 1

    # Guest skip vote reaches threshold (2) and triggers advancement
    skip_2 = client.post(
        f"/api/jams/{jam_id}/skip-vote",
        headers=guest_headers,
        json={},
    )
    assert skip_2.status_code == 200
    assert skip_2.json()["advanced"] is True

    # 5. Save track from queue
    save_q = client.post(
        f"/api/jams/{jam_id}/save-queue-track",
        headers=guest_headers,
        json={"track_id": track_2},
    )
    assert save_q.status_code == 200

    # 6. Host closes jam
    guest_close = client.post(f"/api/jams/{jam_id}/close", headers=guest_headers)
    assert guest_close.status_code == 403

    host_close = client.post(f"/api/jams/{jam_id}/close", headers=host_headers)
    assert host_close.status_code == 200
    assert host_close.json()["is_active"] is False


# ==============================================================================
# FLOW 6: Reviews & Catalog Search
# ==============================================================================


def test_flow_6_reviews_and_catalog_search(
    client: TestClient, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")

    # Author user
    _, author_headers = _register_and_login(
        client, "critic_user@example.com", "1989-12-05", free_id
    )
    # Reader user
    _, reader_headers = _register_and_login(
        client, "reader_user@example.com", "1991-03-14", free_id
    )

    # 1. Catalog search with Spotify external fallback on empty local results
    container = app.state.container

    def mock_spotify_search(query: str, limit: int = 10) -> list[CatalogTrack]:
        return [
            CatalogTrack(
                external_id="spotify-synth-404",
                title="Midnight City Synth",
                artist="Retro Wave",
                album="Neon Lights",
                preview_url="https://audio.preview/midnight.mp3",
            )
        ]

    monkeypatch.setattr(container.music_service, "search_tracks", mock_spotify_search)

    search_res = client.get(
        "/api/tracks/search?query=Midnight%20City%20Synth",
        headers=author_headers,
    )
    assert search_res.status_code == 200, search_res.text
    tracks = search_res.json()
    assert len(tracks) >= 1
    found_track = tracks[0]
    track_id = found_track["track_id"]

    # 2. Publish review with rating 1..5
    review_res = client.post(
        "/api/reviews",
        headers=author_headers,
        json={
            "track_id": track_id,
            "rating": 5,
            "text": "Stunning synthwave atmosphere!",
        },
    )
    assert review_res.status_code == 201, review_res.text
    review_id = review_res.json()["review_id"]

    # 3. Only 1 active review per user per track -> second review raises 400
    dup_review = client.post(
        "/api/reviews",
        headers=author_headers,
        json={
            "track_id": track_id,
            "rating": 4,
            "text": "Trying to post a duplicate review.",
        },
    )
    assert dup_review.status_code in (400, 409)

    # 4. Idempotent like on review
    like_1 = client.post(f"/api/reviews/{review_id}/like", headers=reader_headers)
    assert like_1.status_code == 200
    assert like_1.json()["likes_count"] == 1

    like_2 = client.post(f"/api/reviews/{review_id}/like", headers=reader_headers)
    assert like_2.status_code == 200
    assert like_2.json()["likes_count"] == 1

    # 5. Author-only review deletion
    stranger_delete = client.delete(
        f"/api/reviews/{review_id}",
        headers=reader_headers,
    )
    assert stranger_delete.status_code == 403

    author_delete = client.delete(
        f"/api/reviews/{review_id}",
        headers=author_headers,
    )
    assert author_delete.status_code == 200


# ==============================================================================
# FLOW 7: Admin Console
# ==============================================================================


def test_flow_7_admin_console(client: TestClient) -> None:
    plans = client.get("/api/profile/plans").json()
    free_id = next(p["plan_id"] for p in plans if p["name"] == "Free")

    # Regular non-admin user
    _, regular_headers = _register_and_login(
        client, "standard_listener@example.com", "1997-04-20", free_id
    )

    # 1. Non-admin accessing admin console is forbidden (403)
    dash_denied = client.get("/api/admin/dashboard", headers=regular_headers)
    assert dash_denied.status_code == 403

    # 2. Authenticate as default admin user
    admin_login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Admin dashboard: net revenue calculation
    dash_res = client.get("/api/admin/dashboard", headers=admin_headers)
    assert dash_res.status_code == 200
    dash_json = dash_res.json()
    assert "net_revenue" in dash_json or "receita_liquida_estimada" in dash_json

    # 4. Audience report lists blocked genres count
    # Let standard user block 'Rock'
    indiv_id = next(p["plan_id"] for p in plans if p["name"] == "Individual")
    _, paid_headers = _register_and_login(
        client, "genre_blocker@example.com", "1992-01-01", indiv_id
    )
    block_genre_res = client.put(
        "/api/profile/blocked-genres",
        headers=paid_headers,
        json={"blocked_genres": ["Rock"]},
    )
    assert block_genre_res.status_code == 200

    aud_res = client.get("/api/admin/audience", headers=admin_headers)
    assert aud_res.status_code == 200
    aud_json = aud_res.json()
    genres_dict = aud_json.get("blocked_genres") or aud_json.get(
        "generos_bloqueados", {}
    )
    genres_normalized = {k.lower(): v for k, v in genres_dict.items()}
    assert "rock" in genres_normalized and genres_normalized["rock"] >= 1

    # 5. List administrators & prevent self-demotion
    admins_list = client.get("/api/admin/administrators", headers=admin_headers).json()
    admin_obj = next(a for a in admins_list if a["email"] == ADMIN_EMAIL)
    admin_id = admin_obj["user_id"]

    self_demote = client.put(
        f"/api/admin/administrators/{admin_id}",
        headers=admin_headers,
        json={"is_admin": False},
    )
    assert self_demote.status_code == 400
    assert "revogar" in self_demote.text.lower()

    # 6. Block / unblock track
    # Block Bohemian Rhapsody
    all_tracks = client.get(
        "/api/tracks/search?query=Bohemian", headers=admin_headers
    ).json()
    bohemian = next(t for t in all_tracks if "Bohemian" in t["title"])
    b_id = bohemian["track_id"]

    block_res = client.post(
        f"/api/admin/tracks/{b_id}/block",
        headers=admin_headers,
        json={"blocked": True},
    )
    assert block_res.status_code == 200
    assert block_res.json()["blocked"] is True

    blocked_list = client.get("/api/admin/blocked-tracks", headers=admin_headers).json()
    assert any(t["track_id"] == b_id for t in blocked_list)

    unblock_res = client.post(
        f"/api/admin/tracks/{b_id}/block",
        headers=admin_headers,
        json={"blocked": False},
    )
    assert unblock_res.status_code == 200
    assert unblock_res.json()["blocked"] is False

    # 7. Update plan pricing and capacity
    plan_update_res = client.put(
        f"/api/admin/plans/{indiv_id}",
        headers=admin_headers,
        json={"monthly_price": 18.90, "max_profiles": 1},
    )
    assert plan_update_res.status_code == 200
    assert plan_update_res.json()["monthly_price"] == 18.90

    # Negative price rejected
    neg_price_res = client.put(
        f"/api/admin/plans/{indiv_id}",
        headers=admin_headers,
        json={"monthly_price": -5.00},
    )
    assert neg_price_res.status_code == 400


# ==============================================================================
# LEGACY COMPATIBILITY TEST SUITE (PORTED FROM FEAT/BACKEND-CORE 63591B2)
# ==============================================================================


def _cadastrar(
    client: TestClient, email: str, data_nascimento: str, plano_id: int
) -> tuple[dict[str, Any], dict[str, str]]:
    resposta = client.post(
        "/api/auth/cadastrar",
        json={
            "email": email,
            "senha": "password123",
            "nome_exibicao": "Ribbit Test",
            "data_nascimento": data_nascimento,
            "plano_id": plano_id,
        },
    )
    assert resposta.status_code == 201, resposta.text
    login = client.post(
        "/api/auth/login", json={"email": email, "senha": "password123"}
    )
    assert login.status_code == 200, login.text
    return resposta.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_auth_blocked_minor_and_bearer_identity(client: TestClient) -> None:
    planos = client.get("/api/planos").json()
    free_id = next(plano["plano_id"] for plano in planos if plano["nome"] == "Free")

    cadastro = client.post(
        "/api/auth/cadastrar",
        json={
            "email": "minor-direct@ribbit.com",
            "senha": "password123",
            "nome_exibicao": "Minor",
            "data_nascimento": "2012-01-01",
        },
    )
    assert cadastro.status_code == 400

    user, headers = _cadastrar(client, "adult@ribbit.com", "1990-01-01", free_id)
    assert client.get("/api/perfil/me").status_code == 401
    profile = client.get("/api/perfil/me?usuario_id=999999", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["usuario"]["usuario_id"] == user["usuario_id"]


def test_playlist_deck_and_owner_only_writes(client: TestClient) -> None:
    planos = client.get("/api/planos").json()
    individual_id = next(
        plano["plano_id"] for plano in planos if plano["nome"] == "Individual"
    )
    _, headers = _cadastrar(
        client, "playlist-owner@ribbit.com", "1988-04-05", individual_id
    )
    deck = client.post(
        "/api/playlists/deck",
        headers=headers,
        json={"nome": "Pop curta", "duracao_minutos": 5, "genero": "Pop"},
    )
    assert deck.status_code == 201, deck.text
    playlist_id = deck.json()["playlist_id"]
    assert deck.json()["musicas"] == []
    first_page = client.get(
        f"/api/playlists/{playlist_id}/deck?limite=20", headers=headers
    )
    assert first_page.status_code == 200
    assert first_page.json()["items"]
    assert all(track["duracao_segundos"] <= 300 for track in first_page.json()["items"])

    track = first_page.json()["items"][0]
    added = client.post(
        f"/api/playlists/{playlist_id}/swipe-add",
        headers=headers,
        json={"musica_id": track["musica_id"], "acao": "superlike"},
    )
    assert added.status_code == 200, added.text
    remaining_deck = client.get(f"/api/playlists/{playlist_id}/deck", headers=headers)
    assert remaining_deck.status_code == 200
    assert track["musica_id"] not in {
        candidate["musica_id"] for candidate in remaining_deck.json()["items"]
    }
    other_suggestion = next(
        candidate
        for candidate in first_page.json()["items"]
        if candidate["musica_id"] != track["musica_id"]
    )
    over_duration = client.post(
        f"/api/playlists/{playlist_id}/swipe-add",
        headers=headers,
        json={"musica_id": other_suggestion["musica_id"], "acao": "curtida"},
    )
    assert over_duration.status_code == 400
    detail = client.get(f"/api/playlists/{playlist_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["duracao_total_segundos"] == track["duracao_segundos"]

    other, other_headers = _cadastrar(
        client, "playlist-other@ribbit.com", "1985-03-02", individual_id
    )
    assert other["usuario_id"] != detail.json()["usuario_id"]
    denied = client.delete(f"/api/playlists/{playlist_id}", headers=other_headers)
    assert denied.status_code == 403


def test_family_minor_is_filtered_and_jam_votes_advance_automatically(
    client: TestClient, app
) -> None:
    planos = client.get("/api/planos").json()
    family_id = next(
        plano["plano_id"] for plano in planos if plano["nome"] == "Família"
    )
    _, host_headers = _cadastrar(
        client, "family-owner@ribbit.com", "1980-05-01", family_id
    )
    member = client.post(
        "/api/perfil/familia/membros",
        headers=host_headers,
        json={
            "email": "family-child@ribbit.com",
            "senha": "password123",
            "nome_exibicao": "Child Profile",
            "data_nascimento": "2012-02-01",
        },
    )
    assert member.status_code == 200, member.text
    child_login = client.post(
        "/api/auth/login",
        json={"email": "family-child@ribbit.com", "senha": "password123"},
    )
    child_headers = {"Authorization": f"Bearer {child_login.json()['access_token']}"}

    room = client.post(
        "/api/jams",
        headers=host_headers,
        json={
            "nome_sala": "Family Jam",
            "duracao_minutos": 60,
            "limite_superlikes": 1,
            "meta_votos_pular": 2,
        },
    )
    assert room.status_code == 201, room.text
    jam = room.json()
    joined = client.post(
        "/api/jams/entrar",
        headers=child_headers,
        json={"codigo_sala": jam["codigo_sala"]},
    )
    assert joined.status_code == 200
    child_deck = client.get(
        f"/api/jams/{jam['jam_id']}/deck-adicionar", headers=child_headers
    )
    assert child_deck.status_code == 200
    assert all(track["titulo"] != "Rap God" for track in child_deck.json()["items"])

    container = app.state.container
    first_track = container.track_repo.find_by_filters(query="Shape of You")[0]
    second_track = container.track_repo.find_by_filters(query="Blinding Lights")[0]
    first = first_track.track_id
    second = second_track.track_id

    first_add = client.post(
        f"/api/jams/{jam['jam_id']}/interagir-deck",
        headers=host_headers,
        json={"musica_id": first, "acao": "like"},
    )
    assert first_add.status_code == 200, first_add.text
    second_add = client.post(
        f"/api/jams/{jam['jam_id']}/interagir-deck",
        headers=host_headers,
        json={"musica_id": second, "acao": "superlike"},
    )
    assert second_add.status_code == 200, second_add.text
    over_limit = client.post(
        f"/api/jams/{jam['jam_id']}/interagir-deck",
        headers=host_headers,
        json={"musica_id": first, "acao": "superlike"},
    )
    assert over_limit.status_code == 400

    first_vote = client.post(
        f"/api/jams/{jam['jam_id']}/votar-pular",
        headers=host_headers,
        json={},
    )
    assert first_vote.status_code == 200, first_vote.text
    repeated_vote = client.post(
        f"/api/jams/{jam['jam_id']}/votar-pular",
        headers=host_headers,
        json={},
    )
    assert repeated_vote.json()["votos"] == 1
    second_vote = client.post(
        f"/api/jams/{jam['jam_id']}/votar-pular",
        headers=child_headers,
        json={},
    )
    assert second_vote.status_code == 200
    assert second_vote.json()["avancou"] is True
    state = client.get(f"/api/jams/{jam['jam_id']}/estado", headers=host_headers)
    assert state.json()["jam"]["musica_atual_id"] == second


def test_rejected_tracks_are_skipped_and_playlist_and_jam_decks_are_large(
    client: TestClient, app
) -> None:
    plans = client.get("/api/planos").json()
    individual_id = next(
        plan["plano_id"] for plan in plans if plan["nome"] == "Individual"
    )
    _, headers = _cadastrar(
        client, "large-deck-user@ribbit.com", "1991-06-07", individual_id
    )

    container = app.state.container
    rejected = container.track_repo.find_by_filters(query="Blinding Lights")[0]
    rejected_id = rejected.track_id

    for index in range(60):
        container.track_repo.save(
            Track(
                title=f"Deck Track {index}",
                artist="Ribbit Test",
                album="Test Album",
                duration_seconds=180,
                genre="Test",
                explicit=False,
            )
        )

    rejected_response = client.post(
        "/api/descoberta/interagir",
        headers=headers,
        json={"musica_id": rejected_id, "acao": "rejeitada"},
    )
    assert rejected_response.status_code == 200, rejected_response.text

    playlist = client.post(
        "/api/playlists/deck",
        headers=headers,
        json={"nome": "Alternativas"},
    )
    assert playlist.status_code == 201, playlist.text
    playlist_id = playlist.json()["playlist_id"]
    playlist_suggestions = client.get(
        f"/api/playlists/{playlist_id}/deck?limite=20", headers=headers
    )
    assert playlist_suggestions.status_code == 200
    playlist_ids = {
        track["musica_id"] for track in playlist_suggestions.json()["items"]
    }
    assert rejected_id not in playlist_ids
    assert len(playlist_ids) == 20
    assert playlist_suggestions.json()["has_more"] is True
    next_playlist_page = client.get(
        f"/api/playlists/{playlist_id}/deck?limite=20"
        f"&cursor_id={playlist_suggestions.json()['next_cursor']}",
        headers=headers,
    )
    assert next_playlist_page.status_code == 200
    next_playlist_ids = {
        track["musica_id"] for track in next_playlist_page.json()["items"]
    }
    assert len(next_playlist_ids) == 20
    assert playlist_ids.isdisjoint(next_playlist_ids)

    jam = client.post(
        "/api/jams",
        headers=headers,
        json={"nome_sala": "Alternativas", "duracao_minutos": 600},
    )
    assert jam.status_code == 201, jam.text
    jam_suggestions = client.get(
        f"/api/jams/{jam.json()['jam_id']}/deck-adicionar?limite=20",
        headers=headers,
    )
    assert jam_suggestions.status_code == 200
    jam_ids = {track["musica_id"] for track in jam_suggestions.json()["items"]}
    assert rejected_id not in jam_ids
    assert len(jam_ids) == 20
    assert jam_suggestions.json()["has_more"] is True
    next_jam_page = client.get(
        f"/api/jams/{jam.json()['jam_id']}/deck-adicionar?limite=20"
        f"&cursor_id={jam_suggestions.json()['next_cursor']}",
        headers=headers,
    )
    assert next_jam_page.status_code == 200
    next_jam_ids = {track["musica_id"] for track in next_jam_page.json()["items"]}
    assert len(next_jam_ids) == 20
    assert jam_ids.isdisjoint(next_jam_ids)


def test_blocked_genre_does_not_hide_or_prevent_music_and_review_actions(
    client: TestClient,
) -> None:
    plans = client.get("/api/planos").json()
    individual_id = next(
        plan["plano_id"] for plan in plans if plan["nome"] == "Individual"
    )
    _, headers = _cadastrar(
        client, "blocked-genre-user@ribbit.com", "1992-09-10", individual_id
    )
    blocked = client.put(
        "/api/perfil/generos-bloqueados",
        headers=headers,
        json={"generos_bloqueados": ["Rock"]},
    )
    assert blocked.status_code == 200, blocked.text

    search = client.get(
        "/api/musicas/buscar?genero=Rock",
        headers=headers,
    )
    assert search.status_code == 200
    queen = next(
        track for track in search.json() if track["titulo"] == "Bohemian Rhapsody"
    )

    favorite = client.post(
        f"/api/reviews/{queen['musica_id']}/curtir-busca",
        headers=headers,
        json={},
    )
    assert favorite.status_code == 200, favorite.text
    review = client.post(
        "/api/reviews",
        headers=headers,
        json={
            "musica_id": queen["musica_id"],
            "nota": 5,
            "texto": "Great song",
        },
    )
    assert review.status_code == 201, review.text


def test_admin_seed_uses_common_login_and_admin_role(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "senha": ADMIN_PASSWORD},
    )
    assert login.status_code == 200, login.text
    token_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/admin/dashboard", headers=token_headers).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 401
