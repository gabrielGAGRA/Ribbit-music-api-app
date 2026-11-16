"""Unit tests for Firestore REST client, value encoding, and hybrid cross-machine sync."""

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

from app.application.dtos.review_dtos import PublishReviewCommand
from app.application.use_cases.review.publish_review import PublishReviewUseCase
from app.application.use_cases.user.delete_user_account import DeleteUserAccountUseCase
from app.application.use_cases.user.get_user_profile import GetUserProfileUseCase
from app.application.use_cases.user.list_family_members import ListFamilyMembersUseCase
from app.config import Settings
from app.domain.exceptions import DuplicateEntityError, ExternalServiceError
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
from app.infrastructure.adapters import FirestoreRestClient, FirestoreSyncService
from app.infrastructure.adapters.gcp import firestore_client as firestore_client_mod
from app.infrastructure.adapters.gcp.firestore_client import (
    decode_document,
    decode_firestore_value,
    encode_document_fields,
    encode_firestore_value,
)
from app.infrastructure.adapters.gcp.firestore_sync import (
    review_doc_id,
    track_sync_key,
    user_doc_id,
)
from app.infrastructure.repositories import (
    SCHEMA_PATH,
    SQLiteInteractionRepository,
    SQLiteJamRepository,
    SQLitePlanRepository,
    SQLitePlaylistRepository,
    SQLiteReviewRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    create_connection,
)
from app.infrastructure.repositories.seed import seed_database


class _FakeHttpResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self) -> Any:
        return self._json_data


class _FakeHttpSession:
    def __init__(self, responses: list[_FakeHttpResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> _FakeHttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "params": params,
                "timeout": timeout,
            }
        )
        if not self._responses:
            return _FakeHttpResponse(status_code=200, json_data={})
        return self._responses.pop(0)


class _InMemoryFirestoreClient:
    """In-memory stand-in for FirestoreRestClient implementing the same interface."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def get_document(
        self,
        collection: str,
        doc_id: str,
    ) -> dict[str, Any] | None:
        doc = self.collections.get(collection, {}).get(doc_id)
        return dict(doc) if doc is not None else None

    def upsert_document(
        self,
        collection: str,
        doc_id: str,
        data: Mapping[str, Any],
    ) -> None:
        col = self.collections.setdefault(collection, {})
        stored = dict(data)
        stored["_doc_id"] = doc_id
        col[doc_id] = stored

    def delete_document(self, collection: str, doc_id: str) -> None:
        col = self.collections.get(collection)
        if col is not None:
            col.pop(doc_id, None)

    def list_documents(self, collection: str) -> list[dict[str, Any]]:
        docs = self.collections.get(collection, {}).values()
        return [
            dict(doc) for doc in sorted(docs, key=lambda d: str(d.get("_doc_id") or ""))
        ]

    def query_updated_since(
        self,
        collection: str,
        since_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        docs = self.list_documents(collection)
        if not since_iso:
            return docs
        return [d for d in docs if str(d.get("updated_at") or "") > since_iso]


def _make_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    plan_repo = SQLitePlanRepository(conn)
    plan_repo.save(Plan(name="Free", initial_monthly_price=0.0, initial_max_profiles=1))
    plan_repo.save(
        Plan(name="Ribbit Pro", initial_monthly_price=19.90, initial_max_profiles=1)
    )
    plan_repo.save(
        Plan(name="Família", initial_monthly_price=34.90, initial_max_profiles=6)
    )
    return conn


@pytest.fixture
def two_machines() -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    conn_a = _make_memory_db()
    conn_b = _make_memory_db()
    try:
        yield conn_a, conn_b
    finally:
        conn_a.close()
        conn_b.close()


def test_firestore_value_encode_decode_round_trips() -> None:
    payload = {
        "nothing": None,
        "flag_true": True,
        "flag_false": False,
        "count": 42,
        "ratio": 3.14,
        "label": "ribbit",
        "blob": b"\x89PNG\r\n\x1a\n",
        "tags": ["pop", 1, True],
        "nested": {"inner": "ok", "depth": 2},
    }

    assert encode_firestore_value(None) == {"nullValue": None}
    assert encode_firestore_value(True) == {"booleanValue": True}
    assert encode_firestore_value(42) == {"integerValue": "42"}
    assert encode_firestore_value(3.14) == {"doubleValue": 3.14}

    encoded_fields = encode_document_fields(payload)
    decoded = decode_document(
        {
            "name": "projects/p/databases/(default)/documents/items/item-123",
            "fields": encoded_fields,
        }
    )

    assert decoded["_doc_id"] == "item-123"
    assert decoded["nothing"] is None
    assert decoded["flag_true"] is True
    assert decoded["flag_false"] is False
    assert decoded["count"] == 42
    assert decoded["ratio"] == pytest.approx(3.14)
    assert decoded["label"] == "ribbit"
    assert decoded["blob"] == b"\x89PNG\r\n\x1a\n"
    assert decoded["tags"] == ["pop", 1, True]
    assert decoded["nested"] == {"inner": "ok", "depth": 2}
    assert decode_firestore_value({}) is None


def test_firestore_rest_client_crud_and_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    doc_page_1 = {
        "name": "projects/proj-1/databases/(default)/documents/users/u1",
        "fields": encode_document_fields({"email": "a@example.com"}),
    }
    doc_page_2 = {
        "name": "projects/proj-1/databases/(default)/documents/users/u2",
        "fields": encode_document_fields({"email": "b@example.com"}),
    }
    session = _FakeHttpSession(
        [
            _FakeHttpResponse(status_code=200, json_data={}),
            _FakeHttpResponse(status_code=500, text="boom"),
            _FakeHttpResponse(status_code=404, text="not found"),
            _FakeHttpResponse(status_code=500, text="delete err"),
            _FakeHttpResponse(
                status_code=200,
                json_data={"documents": [doc_page_1], "nextPageToken": "tok-2"},
            ),
            _FakeHttpResponse(
                status_code=200,
                json_data={"documents": [doc_page_2]},
            ),
            _FakeHttpResponse(status_code=404, text="empty collection"),
            _FakeHttpResponse(
                status_code=200,
                json_data=[
                    {"readTime": "2026-01-01T00:00:00Z"},
                    {"document": doc_page_2},
                ],
            ),
            _FakeHttpResponse(status_code=200, json_data=doc_page_1),
            _FakeHttpResponse(status_code=404, text="not found"),
            _FakeHttpResponse(status_code=500, text="get err"),
        ]
    )
    client = FirestoreRestClient(project_id="proj-1", http_session=session)

    client.upsert_document("users", "u1", {"email": "a@example.com", "age": 20})
    assert session.calls[0]["method"] == "PATCH"
    assert session.calls[0]["url"].endswith(
        "/projects/proj-1/databases/(default)/documents/users/u1"
    )
    assert session.calls[0]["headers"] == {"Authorization": "Bearer owner"}
    assert session.calls[0]["json"]["fields"]["age"] == {"integerValue": "20"}

    with pytest.raises(ExternalServiceError) as exc_upsert:
        client.upsert_document("users", "u1", {"email": "a@example.com"})
    assert exc_upsert.value.details["service_name"] == "GCP_Firestore"

    client.delete_document("users", "missing")
    with pytest.raises(ExternalServiceError):
        client.delete_document("users", "u1")

    listed = client.list_documents("users", page_size=1)
    assert [d["email"] for d in listed] == ["a@example.com", "b@example.com"]
    assert session.calls[5]["params"] == {"pageSize": 1, "pageToken": "tok-2"}

    assert client.query_updated_since("users", since_iso=None) == []

    deltas = client.query_updated_since("users", since_iso="2026-01-01T00:00:00Z")
    assert [d["_doc_id"] for d in deltas] == ["u2"]
    assert session.calls[7]["method"] == "POST"
    assert session.calls[7]["url"].endswith(":runQuery")
    where_filter = session.calls[7]["json"]["structuredQuery"]["where"]["fieldFilter"]
    assert where_filter["field"]["fieldPath"] == "updated_at"
    assert where_filter["op"] == "GREATER_THAN"
    assert where_filter["value"] == {"stringValue": "2026-01-01T00:00:00Z"}

    fetched = client.get_document("users", "u1")
    assert fetched is not None
    assert fetched["_doc_id"] == "u1"
    assert fetched["email"] == "a@example.com"
    assert session.calls[8]["method"] == "GET"
    assert client.get_document("users", "missing") is None
    with pytest.raises(ExternalServiceError):
        client.get_document("users", "u1")


def test_cross_computer_hybrid_sync_all_seven_collections(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()

    # Pre-populate Computer B offline rows so its SQLite AUTOINCREMENT IDs diverge from A.
    pre_user_b = SQLiteUserRepository(conn_b).save(
        User(
            email="local_offset@example.com",
            password_hash="pw",
            display_name="Offset",
            plan_id=1,
        )
    )
    pre_track_b = SQLiteTrackRepository(conn_b).save(
        Track(
            title="Local Only",
            artist="Local Artist",
            duration_seconds=120,
            genre="Rock",
            spotify_id="sp_offset_1",
        )
    )
    SQLitePlaylistRepository(conn_b).save(
        Playlist(
            user_id=pre_user_b.user_id or 1,
            name="B Local",
            description="Offset playlist",
            initial_tracks=[pre_track_b],
        )
    )

    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )

    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    track_repo_a = SQLiteTrackRepository(conn_a)
    review_repo_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    playlist_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    interaction_repo_a = SQLiteInteractionRepository(conn_a, sync_service=sync_a)

    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    track_repo_b = SQLiteTrackRepository(conn_b)
    review_repo_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)
    playlist_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
    interaction_repo_b = SQLiteInteractionRepository(conn_b, sync_service=sync_b)

    # Computer A: create users, track, review + like, playlist + image, interaction.
    family_plan = SQLitePlanRepository(conn_a).find_by_name("Família")
    assert family_plan is not None and family_plan.plan_id is not None

    alice_a = user_repo_a.save(
        User(
            email="alice@example.com",
            password_hash="hash_alice",
            display_name="Alice",
            plan_id=family_plan.plan_id,
            favorite_genres=frozenset({"Pop"}),
        )
    )
    assert alice_a.user_id is not None
    bob_a = user_repo_a.save(
        User(
            email="bob@example.com",
            password_hash="hash_bob",
            display_name="Bob",
            plan_id=family_plan.plan_id,
            primary_account_id=alice_a.user_id,
        )
    )
    carol_a = user_repo_a.save(
        User(
            email="carol@example.com",
            password_hash="hash_carol",
            display_name="Carol",
            plan_id=1,
        )
    )
    assert bob_a.user_id is not None and carol_a.user_id is not None

    track_a = track_repo_a.save(
        Track(
            title="Neon Pond",
            artist="Synth Frog",
            album="Night Hop",
            duration_seconds=215,
            genre="Synthwave",
            country="BR",
            release_year=2025,
            cover_url="https://img/neon.jpg",
            itunes_preview_url="https://audio/neon.m4a",
            spotify_id="sp_neon_1",
        )
    )
    assert track_a.track_id is not None

    review_a = review_repo_a.save(
        ReviewComment(
            user_id=carol_a.user_id,
            track_id=track_a.track_id,
            initial_rating=5,
            text="Som incrível!",
        )
    )
    assert review_a.review_id is not None
    review_repo_a.record_like(review_a.review_id, alice_a.user_id)

    playlist_a = playlist_repo_a.save(
        Playlist(
            user_id=alice_a.user_id,
            name="Playlist Verão",
            description="Synced hits",
            initial_tracks=[track_a],
        )
    )
    assert playlist_a.playlist_id is not None
    cover_bytes = b"\x89PNG-synced-cover-bytes"
    assert playlist_repo_a.save_cover_image(
        playlist_a.playlist_id,
        "image/png",
        cover_bytes,
        f"/api/playlists/{playlist_a.playlist_id}/cover",
    )

    interaction_repo_a.save(
        Interaction(
            user_id=bob_a.user_id,
            track_id=track_a.track_id,
            action=InteractionAction.LIKE,
            source="discovery",
        )
    )

    # Computer B reads trigger pull_deltas() and hydrate all 7 collections despite local IDs.
    bob_b = user_repo_b.find_by_email("bob@example.com")
    alice_b = user_repo_b.find_by_email("alice@example.com")
    assert alice_b is not None and alice_b.user_id is not None
    assert alice_b.user_id != alice_a.user_id
    assert bob_b is not None and bob_b.user_id is not None
    assert bob_b.primary_account_id == alice_b.user_id
    assert alice_b.favorite_genres == frozenset({"pop"})

    track_b = track_repo_b.find_by_spotify_id("sp_neon_1")
    assert track_b is not None and track_b.track_id is not None
    assert track_b.track_id != track_a.track_id

    reviews_b = review_repo_b.list_top_recent(days=30, limit=10)
    assert len(reviews_b) == 1
    assert reviews_b[0].text == "Som incrível!"
    assert reviews_b[0].author_name == "Carol"
    assert reviews_b[0].track_title == "Neon Pond"
    assert reviews_b[0].review_id is not None
    assert review_repo_b.has_user_liked(reviews_b[0].review_id, alice_b.user_id) is True

    playlists_b = playlist_repo_b.list_by_user(alice_b.user_id)
    assert len(playlists_b) == 1
    playlist_b = playlists_b[0]
    assert playlist_b.playlist_id is not None
    assert playlist_b.name == "Playlist Verão"
    assert [t.spotify_id for t in playlist_b.tracks] == ["sp_neon_1"]
    assert playlist_repo_b.get_cover_image(playlist_b.playlist_id) == (
        "image/png",
        cover_bytes,
    )

    interactions_b = interaction_repo_b.list_by_user(bob_b.user_id)
    assert len(interactions_b) == 1
    assert interactions_b[0].action == InteractionAction.LIKE
    assert interactions_b[0].track_id == track_b.track_id

    # Mutations & tombstones flow cleanly from B -> A and A -> B.
    assert playlist_repo_b.remove_track(playlist_b.playlist_id, track_b.track_id)
    refreshed_pl_a = playlist_repo_a.find_by_id(playlist_a.playlist_id)
    assert refreshed_pl_a is not None and refreshed_pl_a.tracks == ()

    undone = interaction_repo_b.delete_latest_discovery(bob_b.user_id)
    assert undone is not None
    assert interaction_repo_a.list_by_user(bob_a.user_id) == []

    assert review_repo_a.delete(review_a.review_id)
    assert review_repo_b.list_top_recent(days=30, limit=10) == []

    assert playlist_repo_b.delete(playlist_b.playlist_id)
    assert playlist_repo_a.find_by_id(playlist_a.playlist_id) is None

    assert user_repo_a.delete(bob_a.user_id)
    assert user_repo_b.find_by_email("bob@example.com") is None


def test_sync_all_pushes_preexisting_offline_rows_and_pulls_cloud_data() -> None:
    conn_local = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        # Local offline user created before Firestore was attached.
        local_user = SQLiteUserRepository(conn_local).save(
            User(
                email="offline_user@example.com",
                password_hash="pw",
                display_name="Offline User",
                plan_id=1,
            )
        )
        assert local_user.user_id is not None

        # Cloud already has a remote user.
        cloud.upsert_document(
            "users",
            "remote_at_example.com",
            {
                "email": "remote@example.com",
                "password_hash": "remote_pw",
                "display_name": "Remote User",
                "plan_name": "Free",
                "updated_at": "2026-11-15T12:00:00.000000Z",
            },
        )

        sync = FirestoreSyncService(
            conn=conn_local,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        sync.sync_all()

        remote_on_local = SQLiteUserRepository(conn_local).find_by_email(
            "remote@example.com"
        )
        assert remote_on_local is not None
        assert remote_on_local.display_name == "Remote User"
        assert any(
            doc.get("email") == "offline_user@example.com"
            for doc in cloud.list_documents("users")
        )
    finally:
        conn_local.close()


class _FakeOAuthCreds:
    def __init__(self, *, valid: bool, token: str | None) -> None:
        self.valid = valid
        self.token = token
        self.refresh_calls = 0

    def refresh(self, _request: Any) -> None:
        self.refresh_calls += 1
        self.valid = True
        self.token = "refreshed-token"


def test_firestore_rest_client_oauth_headers_service_account_and_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    sa_file = tmp_path / "sa.json"
    sa_file.write_text("{}", encoding="utf-8")
    sa_creds = _FakeOAuthCreds(valid=False, token=None)
    monkeypatch.setattr(
        firestore_client_mod.service_account.Credentials,
        "from_service_account_file",
        lambda _path, scopes=None: sa_creds,
    )

    session = _FakeHttpSession(
        [
            _FakeHttpResponse(status_code=200, json_data={}),
            _FakeHttpResponse(status_code=200, json_data={}),
        ]
    )
    client_sa = FirestoreRestClient(
        project_id="proj-sa",
        credentials_path=str(sa_file),
        http_session=session,
    )
    client_sa.upsert_document("users", "u1", {"email": "sa@example.com"})
    client_sa.upsert_document("users", "u1", {"email": "sa@example.com"})
    assert sa_creds.refresh_calls == 1
    assert session.calls[0]["headers"] == {"Authorization": "Bearer refreshed-token"}
    assert session.calls[1]["headers"] == {"Authorization": "Bearer refreshed-token"}

    adc_creds = _FakeOAuthCreds(valid=True, token="adc-token-123")
    monkeypatch.setattr(
        firestore_client_mod.google.auth,
        "default",
        lambda scopes=None: (adc_creds, "proj-adc"),
    )
    session_adc = _FakeHttpSession([_FakeHttpResponse(status_code=200, json_data={})])
    client_adc = FirestoreRestClient(project_id="proj-adc", http_session=session_adc)
    client_adc.upsert_document("users", "u2", {"email": "adc@example.com"})
    assert adc_creds.refresh_calls == 0
    assert session_adc.calls[0]["headers"] == {"Authorization": "Bearer adc-token-123"}


def test_cover_image_url_translation_and_oversized_image_suppression(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()

    # Offset local playlist_id on B before syncing.
    bob_b = SQLiteUserRepository(conn_b).save(
        User(
            email="bob_b@example.com",
            password_hash="pw",
            display_name="BobB",
            plan_id=1,
        )
    )
    SQLitePlaylistRepository(conn_b).save(
        Playlist(user_id=bob_b.user_id or 1, name="OffsetB", description="offset")
    )

    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    playlist_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    playlist_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)

    alice_a = user_repo_a.save(
        User(
            email="alice@example.com",
            password_hash="pw",
            display_name="Alice",
            plan_id=1,
        )
    )
    pl_a = playlist_repo_a.save(
        Playlist(user_id=alice_a.user_id or 1, name="Cover Sync", description="desc")
    )
    assert pl_a.playlist_id is not None
    small_cover = b"\x89PNG-small-cover"
    assert playlist_repo_a.save_cover_image(
        pl_a.playlist_id,
        "image/png",
        small_cover,
        f"/api/playlists/{pl_a.playlist_id}/image",
    )

    alice_b = user_repo_b.find_by_email("alice@example.com")
    assert alice_b is not None and alice_b.user_id is not None
    pls_b = playlist_repo_b.list_by_user(alice_b.user_id)
    assert len(pls_b) == 1
    pl_b = pls_b[0]
    assert pl_b.playlist_id is not None and pl_b.playlist_id != pl_a.playlist_id
    assert pl_b.cover_image_url == f"/api/playlists/{pl_b.playlist_id}/image"
    assert playlist_repo_b.get_cover_image(pl_b.playlist_id) == (
        "image/png",
        small_cover,
    )

    # Replacing cover on A with >700 KB suppresses image sync & clears stale cover URL on B.
    oversized = b"\x89PNG" + (b"x" * 750_000)
    assert playlist_repo_a.save_cover_image(
        pl_a.playlist_id,
        "image/png",
        oversized,
        f"/api/playlists/{pl_a.playlist_id}/image",
    )
    assert cloud.list_documents("playlist_images") == []

    refreshed_b = playlist_repo_b.find_by_id(pl_b.playlist_id)
    assert refreshed_b is not None
    assert refreshed_b.cover_image_url is None


def test_source_playlist_id_resolved_across_diverged_machines(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()

    offset_user = SQLiteUserRepository(conn_b).save(
        User(
            email="offset_src@example.com",
            password_hash="pw",
            display_name="O",
            plan_id=1,
        )
    )
    SQLitePlaylistRepository(conn_b).save(
        Playlist(user_id=offset_user.user_id or 1, name="Offset 1", description="o1")
    )
    SQLitePlaylistRepository(conn_b).save(
        Playlist(user_id=offset_user.user_id or 1, name="Offset 2", description="o2")
    )

    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    alice_a = SQLiteUserRepository(conn_a, sync_service=sync_a).save(
        User(
            email="alice_src@example.com",
            password_hash="pw",
            display_name="Alice",
            plan_id=1,
        )
    )
    pl_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    t_now = datetime.now(UTC)
    src_a = pl_repo_a.save(
        Playlist(
            user_id=alice_a.user_id or 1,
            name="Base Source",
            description="source",
            created_at=t_now,
        )
    )
    assert src_a.playlist_id is not None
    deck_a = pl_repo_a.save(
        Playlist(
            user_id=alice_a.user_id or 1,
            name="Deck Child",
            description="derived",
            source_playlist_id=src_a.playlist_id,
            created_at=t_now + timedelta(seconds=1),
        )
    )
    assert deck_a.source_playlist_id == src_a.playlist_id

    # Reverse playlist order in Firestore to ensure pull sorts parent playlists first.
    items = list(cloud.collections["playlists"].items())
    cloud.collections["playlists"] = dict(reversed(items))

    alice_b = SQLiteUserRepository(conn_b, sync_service=sync_b).find_by_email(
        "alice_src@example.com"
    )
    assert alice_b is not None and alice_b.user_id is not None
    pls_b = {
        p.name: p
        for p in SQLitePlaylistRepository(conn_b, sync_service=sync_b).list_by_user(
            alice_b.user_id
        )
    }
    src_b = pls_b["Base Source"]
    deck_b = pls_b["Deck Child"]
    assert src_b.playlist_id is not None and src_b.playlist_id != src_a.playlist_id
    assert deck_b.source_playlist_id == src_b.playlist_id


def test_save_track_replacement_tombstones_and_preserves_order(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )

    alice_a = SQLiteUserRepository(conn_a, sync_service=sync_a).save(
        User(
            email="order@example.com",
            password_hash="pw",
            display_name="Order",
            plan_id=1,
        )
    )
    tr_a = SQLiteTrackRepository(conn_a)
    t1 = tr_a.save(
        Track(
            title="T1",
            artist="A1",
            duration_seconds=100,
            genre="Pop",
            spotify_id="sp_001",
        )
    )
    t2 = tr_a.save(
        Track(
            title="T2",
            artist="A2",
            duration_seconds=100,
            genre="Pop",
            spotify_id="sp_002",
        )
    )
    t3 = tr_a.save(
        Track(
            title="T3",
            artist="A3",
            duration_seconds=100,
            genre="Pop",
            spotify_id="sp_003",
        )
    )

    pl_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    pl_a = pl_repo_a.save(
        Playlist(
            user_id=alice_a.user_id or 1,
            name="Ordered List",
            description="ord",
            initial_tracks=[t1, t3, t2],
        )
    )
    assert pl_a.playlist_id is not None

    # Reverse playlist_tracks doc order in cloud so naive insertion without position would scramble.
    pt_items = list(cloud.collections["playlist_tracks"].items())
    cloud.collections["playlist_tracks"] = dict(reversed(pt_items))

    alice_b = SQLiteUserRepository(conn_b, sync_service=sync_b).find_by_email(
        "order@example.com"
    )
    assert alice_b is not None and alice_b.user_id is not None
    pl_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
    pl_b = pl_repo_b.list_by_user(alice_b.user_id)[0]
    assert [t.spotify_id for t in pl_b.tracks] == ["sp_001", "sp_003", "sp_002"]

    # Replace tracks via save() dropping t1 -> sp_001 tombstoned and [sp_003, sp_002] preserved.
    pl_a.replace_tracks([t3, t2])
    pl_repo_a.save(pl_a)

    pl_b_after = pl_repo_b.find_by_id(pl_b.playlist_id or 0)
    assert pl_b_after is not None
    assert [t.spotify_id for t in pl_b_after.tracks] == ["sp_003", "sp_002"]


def test_concurrent_review_likes_reconcile_and_orphan_likes_buffered(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )

    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    rev_repo_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_repo_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    carol_a = user_repo_a.save(
        User(
            email="carol_l@example.com",
            password_hash="pw",
            display_name="Carol",
            plan_id=1,
        )
    )
    alice_a = user_repo_a.save(
        User(
            email="alice_l@example.com",
            password_hash="pw",
            display_name="Alice",
            plan_id=1,
        )
    )
    user_repo_a.save(
        User(
            email="bob_l@example.com", password_hash="pw", display_name="Bob", plan_id=1
        )
    )
    track_a = SQLiteTrackRepository(conn_a).save(
        Track(
            title="Like Song",
            artist="Frog",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_like_1",
        )
    )
    rev_a = rev_repo_a.save(
        ReviewComment(
            user_id=carol_a.user_id or 1,
            track_id=track_a.track_id or 1,
            initial_rating=5,
            text="Great!",
        )
    )
    assert rev_a.review_id is not None

    # Both machines pull base review before liking concurrently.
    bob_b = user_repo_b.find_by_email("bob_l@example.com")
    alice_b = user_repo_b.find_by_email("alice_l@example.com")
    assert bob_b is not None and bob_b.user_id is not None
    assert alice_b is not None and alice_b.user_id is not None
    rev_b = rev_repo_b.list_top_recent(days=30, limit=10)[0]
    assert rev_b.review_id is not None

    # Concurrent likes before pulling each other: each updates likes_count=1 and records like.
    rev_a.like()
    rev_repo_a.save(rev_a)
    rev_repo_a.record_like(rev_a.review_id, alice_a.user_id or 1)

    rev_b.like()
    rev_repo_b.save(rev_b)
    rev_repo_b.record_like(rev_b.review_id, bob_b.user_id)

    assert rev_repo_b.has_user_liked(rev_b.review_id, alice_b.user_id) is True
    synced_b = rev_repo_b.list_top_recent(days=30, limit=10)[0]
    synced_a = rev_repo_a.list_top_recent(days=30, limit=10)[0]
    assert synced_b.likes_count == 2
    assert synced_a.likes_count == 2

    # Orphan review_like arriving before its parent review is buffered without advancing watermark.
    conn_c = _make_memory_db()
    try:
        orphan_cloud = _InMemoryFirestoreClient()
        sync_c = FirestoreSyncService(
            conn=conn_c,
            client=orphan_cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        orphan_cloud.upsert_document(
            "review_likes",
            "orphan-like-1",
            {
                "review_user_email": "author_o@example.com",
                "review_created_at": "2026-11-15T10:00:00.000000Z",
                "user_email": "liker_o@example.com",
                "track_spotify_id": "sp_orphan_1",
                "track_title": "Orphan Track",
                "track_artist": "Artist O",
                "updated_at": "2026-11-15T10:00:01.000000Z",
            },
        )
        assert sync_c.pull_deltas() is True
        assert "review_likes" not in sync_c._watermarks
        assert len(sync_c._pending_review_likes) == 1

        orphan_cloud.upsert_document(
            "reviews",
            "orphan-rev-1",
            {
                "user_email": "author_o@example.com",
                "author_name": "Author O",
                "rating": 4,
                "text": "Arrived late",
                "likes_count": 0,
                "is_deleted": False,
                "created_at": "2026-11-15T10:00:00.000000Z",
                "updated_at": "2026-11-15T10:01:00.000000Z",
                "track_spotify_id": "sp_orphan_1",
                "track_title": "Orphan Track",
                "track_artist": "Artist O",
                "track_duration_seconds": 180,
                "track_genre": "Pop",
            },
        )
        assert sync_c.pull_deltas() is True
        assert sync_c._pending_review_likes == {}
        assert "review_likes" in sync_c._watermarks
        reviews_c = SQLiteReviewRepository(conn_c).list_top_recent(days=3650, limit=10)
        assert len(reviews_c) == 1 and reviews_c[0].likes_count == 1
    finally:
        conn_c.close()


def test_savepoint_isolation_cooldown_on_failure_and_sync_all_guard() -> None:
    conn = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        sync = FirestoreSyncService(
            conn=conn,
            client=cloud,
            min_pull_interval_seconds=60.0,  # type: ignore[arg-type]
        )
        user_repo = SQLiteUserRepository(conn)
        track = SQLiteTrackRepository(conn).save(
            Track(
                title="Unique Track",
                artist="Artist",
                duration_seconds=180,
                genre="Pop",
                spotify_id="sp_uq",
            )
        )
        holder = user_repo.save(
            User(
                email="holder@example.com",
                password_hash="pw",
                display_name="Holder",
                plan_id=1,
                spotify_id="sp_taken",
            )
        )
        SQLiteReviewRepository(conn).save(
            ReviewComment(
                user_id=holder.user_id or 1,
                track_id=track.track_id or 1,
                initial_rating=3,
                text="Existing active review",
            )
        )

        future_ts = (datetime.now(UTC) + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        cloud.upsert_document(
            "users",
            "claimer",
            {
                "email": "claimer@example.com",
                "password_hash": "pw",
                "display_name": "Claimer",
                "spotify_id": "sp_taken",
                "plan_name": "Free",
                "updated_at": future_ts,
            },
        )
        cloud.upsert_document(
            "users",
            "innocent",
            {
                "email": "innocent@example.com",
                "password_hash": "pw",
                "display_name": "Innocent",
                "plan_name": "Free",
                "updated_at": future_ts,
            },
        )
        # Re-activating another timestamp review on same (user, track) resolves cleanly.
        cloud.upsert_document(
            "reviews",
            "conflict_rev",
            {
                "user_email": "holder@example.com",
                "author_name": "Holder",
                "rating": 5,
                "text": "Newer active",
                "likes_count": 0,
                "is_deleted": False,
                "created_at": "2026-11-15T11:00:00.000000Z",
                "updated_at": "2026-11-15T11:00:00.000000Z",
                "track_spotify_id": "sp_uq",
                "track_title": "Unique Track",
                "track_artist": "Artist",
                "track_duration_seconds": 180,
                "track_genre": "Pop",
            },
        )
        # Malformed doc causing ValueError in handler is rolled back inside its savepoint only.
        cloud.upsert_document(
            "users",
            "bad_age",
            {
                "email": "bad_age@example.com",
                "password_hash": "pw",
                "plan_id": "not-an-int",
                "updated_at": "2026-11-15T11:00:00.000000Z",
            },
        )

        assert sync.pull_deltas(force=True) is True
        assert user_repo.find_by_email("innocent@example.com") is not None
        claimer = user_repo.find_by_email("claimer@example.com")
        assert claimer is not None and claimer.spotify_id == "sp_taken"
        # Watermark must be capped to <= local UTC now despite future_ts.
        assert sync._watermarks["users"] < future_ts

        # Failed pull must not advance _last_pull_mono, and sync_all must not push local state.
        class _FailingClient(_InMemoryFirestoreClient):
            def __init__(self) -> None:
                super().__init__()
                self.upsert_calls = 0

            def upsert_document(
                self, collection: str, doc_id: str, data: Mapping[str, Any]
            ) -> None:
                self.upsert_calls += 1

            def query_updated_since(
                self, collection: str, since_iso: str | None = None
            ) -> list[dict[str, Any]]:
                raise ExternalServiceError("offline", service_name="GCP_Firestore")

        failing_client = _FailingClient()
        failing_sync = FirestoreSyncService(
            conn=conn,
            client=failing_client,
            min_pull_interval_seconds=60.0,  # type: ignore[arg-type]
        )
        assert failing_sync.pull_deltas() is False
        assert failing_sync._last_pull_mono is None
        failing_sync.sync_all()
        assert failing_client.upsert_calls == 0
    finally:
        conn.close()


def test_concurrent_save_and_pull_deltas_on_thread_safe_connection(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "shared_concurrent.db"
    conn = create_connection(str(db_file))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        plan_repo = SQLitePlanRepository(conn)
        plan_repo.save(
            Plan(name="Free", initial_monthly_price=0.0, initial_max_profiles=1)
        )
        cloud = _InMemoryFirestoreClient()
        sync = FirestoreSyncService(
            conn=conn,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        user_repo = SQLiteUserRepository(conn, sync_service=sync)
        pl_repo = SQLitePlaylistRepository(conn, sync_service=sync)
        user = user_repo.save(
            User(
                email="conc@example.com",
                password_hash="pw",
                display_name="Conc",
                plan_id=1,
            )
        )
        t1 = SQLiteTrackRepository(conn).save(
            Track(
                title="CT1",
                artist="CA",
                duration_seconds=120,
                genre="Pop",
                spotify_id="sp_c1",
            )
        )
        pl = pl_repo.save(
            Playlist(
                user_id=user.user_id or 1,
                name="Conc-0",
                description="shared",
                initial_tracks=[t1],
            )
        )
        assert pl.playlist_id is not None

        errors: list[BaseException] = []

        def _writer() -> None:
            try:
                for i in range(1, 21):
                    pl.name = f"Conc-{i}"
                    pl_repo.save(pl)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def _puller() -> None:
            try:
                for i in range(20):
                    cloud.upsert_document(
                        "users",
                        f"peer_{i}",
                        {
                            "email": f"peer_{i}@example.com",
                            "password_hash": "pw",
                            "display_name": f"Peer {i}",
                            "plan_name": "Free",
                            "updated_at": datetime.now(UTC).strftime(
                                "%Y-%m-%dT%H:%M:%S.%fZ"
                            ),
                        },
                    )
                    if i % 3 == 0:
                        cloud.upsert_document(
                            "users",
                            f"bad_{i}",
                            {"email": f"bad_{i}@example.com", "plan_id": "bad"},
                        )
                    sync.pull_deltas(force=True)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        w_thread = threading.Thread(target=_writer)
        p_thread = threading.Thread(target=_puller)
        w_thread.start()
        p_thread.start()
        w_thread.join()
        p_thread.join()

        assert errors == []
        final_pl = pl_repo.find_by_id(pl.playlist_id)
        assert final_pl is not None
        assert final_pl.name == "Conc-20"
    finally:
        conn.close()


def test_review_delete_and_recreate_pulls_out_of_order_without_hijacking_likes(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    rev_repo_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_repo_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    alice_a = user_repo_a.save(
        User(
            email="alice_oo@example.com",
            password_hash="pw",
            display_name="Alice",
            plan_id=1,
        )
    )
    bob_b = user_repo_b.save(
        User(
            email="bob_oo@example.com",
            password_hash="pw",
            display_name="Bob",
            plan_id=1,
        )
    )
    assert alice_a.user_id is not None and bob_b.user_id is not None

    track_a = SQLiteTrackRepository(conn_a).save(
        Track(
            title="ReReview Song",
            artist="ReReview Artist",
            duration_seconds=200,
            genre="Pop",
            spotify_id="sp_rev_oo",
        )
    )
    assert track_a.track_id is not None

    t1 = datetime.now(UTC) - timedelta(seconds=30)
    rev_a1 = rev_repo_a.save(
        ReviewComment(
            user_id=alice_a.user_id,
            track_id=track_a.track_id,
            initial_rating=4,
            text="First take",
            created_at=t1,
        )
    )
    assert rev_a1.review_id is not None

    # Machine B pulls R1 and Bob likes it.
    rev_b1_list = rev_repo_b.list_top_recent(days=30, limit=10)
    assert len(rev_b1_list) == 1
    rev_b1 = rev_b1_list[0]
    assert rev_b1.review_id is not None
    rev_repo_b.record_like(rev_b1.review_id, bob_b.user_id)

    # Alice deletes R1 and publishes R2 on Machine A.
    rev_repo_a.delete(rev_a1.review_id)
    rev_repo_a.save(
        ReviewComment(
            user_id=alice_a.user_id,
            track_id=track_a.track_id,
            initial_rating=5,
            text="Replacement take",
            created_at=datetime.now(UTC),
        )
    )

    # Force Firestore iteration order so R2 (is_deleted=False) appears before R1 (is_deleted=True).
    reordered = sorted(
        cloud.collections["reviews"].items(),
        key=lambda item: 0 if not item[1].get("is_deleted") else 1,
    )
    cloud.collections["reviews"] = dict(reordered)

    assert sync_b.pull_deltas(force=True) is True
    active_b = rev_repo_b.list_top_recent(days=30, limit=10)
    assert len(active_b) == 1
    rev_b2 = active_b[0]
    assert rev_b2.review_id is not None
    assert rev_b2.review_id != rev_b1.review_id
    assert rev_b2.likes_count == 0
    assert rev_b2.text == "Replacement take"
    assert rev_repo_b.has_user_liked(rev_b2.review_id, bob_b.user_id) is False

    old_row = conn_b.execute(
        "SELECT is_deleted, likes_count FROM reviews WHERE review_id = ?",
        (rev_b1.review_id,),
    ).fetchone()
    assert old_row is not None
    assert old_row["is_deleted"] == 1
    assert old_row["likes_count"] == 1


def test_deleted_account_children_do_not_resurrect_on_reregistration(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    pl_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    pl_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
    rev_repo_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_repo_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)
    int_repo_a = SQLiteInteractionRepository(conn_a, sync_service=sync_a)
    int_repo_b = SQLiteInteractionRepository(conn_b, sync_service=sync_b)

    past = datetime.now(UTC) - timedelta(minutes=10)
    alice_a = user_repo_a.save(
        User(
            email="alice_del@example.com",
            password_hash="pw1",
            display_name="Alice One",
            plan_id=1,
            created_at=past,
        )
    )
    assert alice_a.user_id is not None
    track_a = SQLiteTrackRepository(conn_a).save(
        Track(
            title="Secret Song",
            artist="Secret Artist",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_secret_1",
        )
    )
    assert track_a.track_id is not None
    pl_repo_a.save(
        Playlist(
            user_id=alice_a.user_id,
            name="Secret Old Playlist",
            description="private",
            created_at=past + timedelta(minutes=1),
            initial_tracks=[track_a],
        )
    )
    rev_repo_a.save(
        ReviewComment(
            user_id=alice_a.user_id,
            track_id=track_a.track_id,
            initial_rating=5,
            text="Old secret review",
            created_at=past + timedelta(minutes=2),
        )
    )
    int_repo_a.save(
        Interaction(
            user_id=alice_a.user_id,
            track_id=track_a.track_id,
            action=InteractionAction.SUPERLIKE,
            created_at=past + timedelta(minutes=3),
        )
    )

    # Machine B caches Alice's old account and entities before deletion.
    alice_b_old = user_repo_b.find_by_email("alice_del@example.com")
    assert alice_b_old is not None and alice_b_old.user_id is not None
    assert len(pl_repo_b.list_by_user(alice_b_old.user_id)) == 1

    # Alice deletes her account on Machine A, and an offline stray pre-deletion playlist remains.
    assert user_repo_a.delete(alice_a.user_id) is True
    cloud.upsert_document(
        "playlists",
        "stray-old-pl",
        {
            "sync_key": "stray-old-pl",
            "user_email": "alice_del@example.com",
            "name": "Stray Pre-Deletion Playlist",
            "created_at": (past + timedelta(minutes=4)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "is_deleted": False,
            "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        },
    )

    # Same email re-registers after deletion.
    reborn_a = user_repo_a.save(
        User(
            email="alice_del@example.com",
            password_hash="pw2",
            display_name="Alice Reborn",
            plan_id=1,
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    assert reborn_a.user_id is not None
    assert sync_a.pull_deltas(force=True) is True
    assert pl_repo_a.list_by_user(reborn_a.user_id) == []
    assert rev_repo_a.list_by_track(track_a.track_id, limit=10) == []
    assert int_repo_a.list_by_user(reborn_a.user_id) == []

    # Machine B pulls deletion + re-registration and must also lose all old entities.
    reborn_b = user_repo_b.find_by_email("alice_del@example.com")
    assert reborn_b is not None and reborn_b.user_id is not None
    assert reborn_b.display_name == "Alice Reborn"
    assert pl_repo_b.list_by_user(reborn_b.user_id) == []
    track_b = SQLiteTrackRepository(conn_b).find_by_spotify_id("sp_secret_1")
    assert track_b is not None and track_b.track_id is not None
    assert rev_repo_b.list_by_track(track_b.track_id, limit=10) == []
    assert int_repo_b.list_by_user(reborn_b.user_id) == []


def test_seeded_track_without_spotify_id_enriched_and_removal_persists(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    user_repo_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    user_repo_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    pl_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    pl_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
    track_repo_a = SQLiteTrackRepository(conn_a)
    track_repo_b = SQLiteTrackRepository(conn_b)

    # Machine B has a pre-seeded local track with spotify_id=None.
    seeded_b = track_repo_b.save(
        Track(
            title="Seeded Classic",
            artist="Pond Band",
            duration_seconds=210,
            genre="Indie",
            spotify_id=None,
        )
    )
    assert seeded_b.track_id is not None

    # Machine A has the same track with spotify_id populated in a playlist.
    alice_a = user_repo_a.save(
        User(
            email="seed_user@example.com",
            password_hash="pw",
            display_name="SeedUser",
            plan_id=1,
        )
    )
    assert alice_a.user_id is not None
    track_a = track_repo_a.save(
        Track(
            title="Seeded Classic",
            artist="Pond Band",
            duration_seconds=210,
            genre="Indie",
            spotify_id="sp_seeded_1",
        )
    )
    pl_a = pl_repo_a.save(
        Playlist(
            user_id=alice_a.user_id,
            name="Shared Mix",
            initial_tracks=[track_a],
        )
    )
    assert pl_a.playlist_id is not None

    # Machine B pulls: seeded local track receives spotify_id backfill.
    alice_b = user_repo_b.find_by_email("seed_user@example.com")
    assert alice_b is not None and alice_b.user_id is not None
    enriched_b = track_repo_b.find_by_id(seeded_b.track_id)
    assert enriched_b is not None and enriched_b.spotify_id == "sp_seeded_1"

    playlists_b = pl_repo_b.list_by_user(alice_b.user_id)
    assert len(playlists_b) == 1
    pl_b = playlists_b[0]
    assert pl_b.playlist_id is not None
    assert len(pl_b.tracks) == 1

    # Remove track on Machine B and verify removal persists across pulls on both machines.
    pl_b.replace_tracks([])
    pl_repo_b.save(pl_b)
    assert sync_b.pull_deltas(force=True) is True
    assert sync_a.pull_deltas(force=True) is True

    final_b = pl_repo_b.find_by_id(pl_b.playlist_id)
    final_a = pl_repo_a.find_by_id(pl_a.playlist_id)
    assert final_b is not None and final_b.tracks == ()
    assert final_a is not None and final_a.tracks == ()


def test_concurrent_track_bulk_upsert_jam_advance_and_bounded_orphan_likes(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "shared_non_synced_repos.db"
    conn = create_connection(str(db_file))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        SQLitePlanRepository(conn).save(
            Plan(name="Free", initial_monthly_price=0.0, initial_max_profiles=1)
        )
        cloud = _InMemoryFirestoreClient()
        sync = FirestoreSyncService(
            conn=conn,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        user_repo = SQLiteUserRepository(conn, sync_service=sync)
        track_repo = SQLiteTrackRepository(conn)
        jam_repo = SQLiteJamRepository(conn)

        host = user_repo.save(
            User(
                email="jam_host@example.com",
                password_hash="pw",
                display_name="Host",
                plan_id=1,
            )
        )
        assert host.user_id is not None
        seed_tracks = [
            track_repo.save(
                Track(
                    title=f"Jam Seed {i}",
                    artist="Artist",
                    duration_seconds=180,
                    genre="Pop",
                    spotify_id=f"sp_jseed_{i}",
                )
            )
            for i in range(12)
        ]
        assert seed_tracks[0].track_id is not None
        jam = jam_repo.save(
            Jam.create(host_user_id=host.user_id, room_name=" Pond Sync ")
        )
        assert jam.jam_id is not None
        jam_id = jam.jam_id
        for tr in seed_tracks[1:]:
            assert tr.track_id is not None
            jam_repo.save_queue_item(JamQueueItem(jam_id=jam_id, track_id=tr.track_id))

        errors: list[BaseException] = []

        def _writer() -> None:
            try:
                for idx in range(1, 11):
                    track_repo.bulk_upsert_tracks(
                        [
                            Track(
                                title=f"Bulk Track {idx}",
                                artist="Bulk Artist",
                                duration_seconds=190,
                                genre="Rock",
                                spotify_id=f"sp_bulk_{idx}",
                            )
                        ]
                    )
                    next_tr_id = seed_tracks[idx].track_id
                    assert next_tr_id is not None
                    jam_repo.advance_playback(jam_id, next_tr_id, next_tr_id)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def _puller() -> None:
            try:
                for idx in range(15):
                    cloud.upsert_document(
                        "users",
                        f"u_conc_{idx}",
                        {
                            "email": f"u_conc_{idx}@example.com",
                            "password_hash": "pw",
                            "display_name": f"User {idx}",
                            "plan_name": "Free",
                            "updated_at": datetime.now(UTC).strftime(
                                "%Y-%m-%dT%H:%M:%S.%fZ"
                            ),
                        },
                    )
                    if idx % 3 == 0:
                        cloud.upsert_document(
                            "users",
                            f"bad_conc_{idx}",
                            {"email": f"bad_conc_{idx}@example.com", "plan_id": "bad"},
                        )
                    sync.pull_deltas(force=True)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        w_thread = threading.Thread(target=_writer)
        p_thread = threading.Thread(target=_puller)
        w_thread.start()
        p_thread.start()
        w_thread.join()
        p_thread.join()

        assert errors == []
        updated_jam = jam_repo.find_by_id(jam_id)
        assert updated_jam is not None
        assert updated_jam.current_track_id == seed_tracks[10].track_id
        assert track_repo.count_all() == 22

        # Permanently unresolvable orphan like must evict after 3 pulls so watermark advances.
        orphan_ts = "2026-11-15T10:00:01.000000Z"
        cloud.upsert_document(
            "review_likes",
            "permanent-orphan-like",
            {
                "review_user_email": "missing_author@example.com",
                "review_created_at": "2026-11-15T10:00:00.000000Z",
                "user_email": "missing_liker@example.com",
                "track_spotify_id": "sp_missing_1",
                "track_title": "Missing",
                "track_artist": "Nobody",
                "updated_at": orphan_ts,
            },
        )
        assert sync.pull_deltas(force=True) is True
        assert "review_likes" not in sync._watermarks
        assert len(sync._pending_review_likes) == 1

        assert sync.pull_deltas(force=True) is True
        assert "review_likes" not in sync._watermarks
        assert len(sync._pending_review_likes) == 1

        assert sync.pull_deltas(force=True) is True
        assert sync._pending_review_likes == {}
        assert sync._pending_like_attempts == {}
        assert sync._watermarks["review_likes"] == orphan_ts
    finally:
        conn.close()


class _FailingChildDeleteClient(_InMemoryFirestoreClient):
    """Test double that fails deleting playlist documents during user purge."""

    def __init__(self, failing_collection: str = "playlists") -> None:
        super().__init__()
        self._failing_collection = failing_collection

    def delete_document(self, collection: str, doc_id: str) -> None:
        if collection == self._failing_collection:
            raise ExternalServiceError(
                "transient child delete failure",
                service_name="GCP_Firestore",
            )
        super().delete_document(collection, doc_id)


def test_family_dependent_sorts_before_primary_across_reregistration(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    assert user_doc_id("bob@example.com") < user_doc_id("alice@example.com")
    conn_a, conn_b = two_machines
    conn_c = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        sync_a = FirestoreSyncService(
            conn=conn_a,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        sync_b = FirestoreSyncService(
            conn=conn_b,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        sync_c = FirestoreSyncService(
            conn=conn_c,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
        u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
        u_c = SQLiteUserRepository(conn_c, sync_service=sync_c)
        pl_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
        pl_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
        pl_c = SQLitePlaylistRepository(conn_c, sync_service=sync_c)

        past = datetime.now(UTC) - timedelta(hours=2)
        alice_old = u_a.save(
            User(
                email="alice@example.com",
                password_hash="pw1",
                display_name="Alice Old",
                plan_id=3,
                created_at=past,
            )
        )
        assert alice_old.user_id is not None
        bob_a = u_a.save(
            User(
                email="bob@example.com",
                password_hash="pw_bob",
                display_name="Bob Child",
                plan_id=3,
                primary_account_id=alice_old.user_id,
                created_at=past + timedelta(minutes=1),
            )
        )
        assert bob_a.user_id is not None
        pl_a.save(
            Playlist(
                user_id=alice_old.user_id,
                name="Old Family List",
                created_at=past + timedelta(minutes=2),
            )
        )

        # Machine C caches old primary, dependent link, and old playlist.
        assert sync_c.pull_deltas(force=True) is True
        alice_c_old = u_c.find_by_email("alice@example.com")
        bob_c_old = u_c.find_by_email("bob@example.com")
        assert alice_c_old is not None and bob_c_old is not None
        assert bob_c_old.primary_account_id == alice_c_old.user_id

        # Delete & re-register primary account, create a new playlist, re-link dependent.
        assert u_a.delete(alice_old.user_id) is True
        reborn_ts = datetime.now(UTC) + timedelta(seconds=1)
        alice_reborn = u_a.save(
            User(
                email="alice@example.com",
                password_hash="pw2",
                display_name="Alice Reborn",
                plan_id=3,
                created_at=reborn_ts,
            )
        )
        assert alice_reborn.user_id is not None
        pl_a.save(
            Playlist(
                user_id=alice_reborn.user_id,
                name="New Family List",
                created_at=reborn_ts + timedelta(seconds=1),
            )
        )
        bob_refreshed = u_a.find_by_id(bob_a.user_id)
        assert bob_refreshed is not None
        bob_refreshed.primary_account_id = alice_reborn.user_id
        u_a.save(bob_refreshed)

        # Fresh Machine B pulls everything in __name__ order (bob < alice).
        assert sync_b.pull_deltas(force=True) is True
        alice_b = u_b.find_by_email("alice@example.com")
        bob_b = u_b.find_by_email("bob@example.com")
        assert alice_b is not None and alice_b.user_id is not None
        assert alice_b.display_name == "Alice Reborn"
        assert alice_b.created_at.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ) == reborn_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        assert bob_b is not None and bob_b.primary_account_id == alice_b.user_id
        assert [p.name for p in pl_b.list_by_user(alice_b.user_id)] == [
            "New Family List"
        ]

        # Caching Machine C pulls and purges old primary while keeping dependent re-linked.
        assert sync_c.pull_deltas(force=True) is True
        alice_c = u_c.find_by_email("alice@example.com")
        bob_c = u_c.find_by_email("bob@example.com")
        assert alice_c is not None and alice_c.user_id is not None
        assert alice_c.display_name == "Alice Reborn"
        assert bob_c is not None and bob_c.primary_account_id == alice_c.user_id
        assert [p.name for p in pl_c.list_by_user(alice_c.user_id)] == [
            "New Family List"
        ]
    finally:
        conn_c.close()


def test_seeded_track_review_and_interaction_deletion_after_spotify_enrichment(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    tr_a = SQLiteTrackRepository(conn_a)
    tr_b = SQLiteTrackRepository(conn_b)
    rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)
    int_a = SQLiteInteractionRepository(conn_a, sync_service=sync_a)
    int_b = SQLiteInteractionRepository(conn_b, sync_service=sync_b)

    author_a = u_a.save(
        User(
            email="rev_author@example.com",
            password_hash="pw",
            display_name="Author",
            plan_id=1,
        )
    )
    liker_a = u_a.save(
        User(
            email="rev_liker@example.com",
            password_hash="pw",
            display_name="Liker",
            plan_id=1,
        )
    )
    assert author_a.user_id is not None and liker_a.user_id is not None

    seeded = tr_a.save(
        Track(
            title="Seeded Song",
            artist="Seeded Artist",
            duration_seconds=180,
            genre="Indie",
            spotify_id=None,
        )
    )
    assert seeded.track_id is not None
    ta_key = track_sync_key(None, "Seeded Song", "Seeded Artist")

    created_ts = datetime.now(UTC) - timedelta(minutes=5)
    review = rev_a.save(
        ReviewComment(
            user_id=author_a.user_id,
            track_id=seeded.track_id,
            initial_rating=5,
            text="Pre-enrichment review",
            created_at=created_ts,
        )
    )
    assert review.review_id is not None
    rev_a.record_like(review.review_id, liker_a.user_id)
    int_a.save(
        Interaction(
            user_id=author_a.user_id,
            track_id=seeded.track_id,
            action=InteractionAction.LIKE,
            created_at=created_ts,
            source="discovery",
        )
    )

    old_rev_doc_id = review_doc_id(
        "rev_author@example.com",
        ta_key,
        created_ts.isoformat(),
    )
    old_like_doc_id = f"{old_rev_doc_id}__{user_doc_id('rev_liker@example.com')}"
    old_int_doc_id = f"{user_doc_id('rev_author@example.com')}__{ta_key}"
    assert cloud.get_document("reviews", old_rev_doc_id) is not None
    assert cloud.get_document("review_likes", old_like_doc_id) is not None
    assert cloud.get_document("interactions", old_int_doc_id) is not None

    # Caching Machine B pulls pre-enrichment active review and interaction.
    assert sync_b.pull_deltas(force=True) is True
    author_b = u_b.find_by_email("rev_author@example.com")
    track_b_row = conn_b.execute(
        "SELECT track_id FROM tracks WHERE lower(title) = 'seeded song'"
    ).fetchone()
    assert author_b is not None and author_b.user_id is not None
    assert track_b_row is not None
    track_b_id = int(track_b_row["track_id"])
    assert len(rev_b.list_by_track(track_b_id, limit=10)) == 1
    assert len(int_b.list_by_user(author_b.user_id)) == 1

    # Enrich track with spotify_id, re-push like (rewriting review_likes under sp_),
    # then delete both review and interaction.
    seeded.spotify_id = "sp_enriched_1"
    tr_a.save(seeded)
    rev_a.record_like(review.review_id, liker_a.user_id)
    assert cloud.get_document("review_likes", old_like_doc_id) is None

    assert rev_a.delete(review.review_id) is True
    assert int_a.delete_latest_discovery(author_a.user_id) is not None
    assert cloud.get_document("reviews", old_rev_doc_id) is None
    assert cloud.get_document("interactions", old_int_doc_id) is None

    # Inject stale offline ta_ docs (ta_ > sp_) to test pull deduplication.
    stale_rev_copy = dict(cloud.list_documents("reviews")[0])
    stale_rev_copy["_doc_id"] = old_rev_doc_id
    stale_rev_copy["track_spotify_id"] = None
    stale_rev_copy["is_deleted"] = False
    stale_rev_copy["updated_at"] = created_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cloud.upsert_document("reviews", old_rev_doc_id, stale_rev_copy)

    stale_int_copy = dict(cloud.list_documents("interactions")[0])
    stale_int_copy["_doc_id"] = old_int_doc_id
    stale_int_copy["track_spotify_id"] = None
    stale_int_copy["is_deleted"] = False
    stale_int_copy["action"] = "LIKE"
    stale_int_copy["updated_at"] = created_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cloud.upsert_document("interactions", old_int_doc_id, stale_int_copy)

    # Caching Machine B clears both review and interaction after enrichment.
    assert sync_b.pull_deltas(force=True) is True
    assert rev_b.list_by_track(track_b_id, limit=10) == []
    assert int_b.list_by_user(author_b.user_id) == []

    # Fresh Machine C pulling in __name__ order deduplicates and stays clean.
    conn_c = _make_memory_db()
    try:
        sync_c = FirestoreSyncService(
            conn=conn_c,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        assert sync_c.pull_deltas(force=True) is True
        author_c = SQLiteUserRepository(conn_c, sync_service=sync_c).find_by_email(
            "rev_author@example.com"
        )
        assert author_c is not None and author_c.user_id is not None
        assert tr_b.find_by_ids([track_b_id]) != []
        active_rev_count = conn_c.execute(
            "SELECT COUNT(*) FROM reviews WHERE is_deleted = 0"
        ).fetchone()[0]
        assert active_rev_count == 0
        assert (
            SQLiteInteractionRepository(conn_c, sync_service=sync_c).list_by_user(
                author_c.user_id
            )
            == []
        )
    finally:
        conn_c.close()


def test_cross_machine_reregistration_preserves_deleted_at_and_partial_child_delete(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    conn_c = _make_memory_db()
    conn_fail = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        sync_a = FirestoreSyncService(
            conn=conn_a,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        sync_b = FirestoreSyncService(
            conn=conn_b,
            client=cloud,
            min_pull_interval_seconds=60.0,  # type: ignore[arg-type]
        )
        sync_c = FirestoreSyncService(
            conn=conn_c,
            client=cloud,
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
        u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
        u_c = SQLiteUserRepository(conn_c, sync_service=sync_c)
        pl_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
        pl_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)
        pl_c = SQLitePlaylistRepository(conn_c, sync_service=sync_c)

        # Trigger initial pull on B so it is now inside the 60s pull cooldown.
        assert sync_b.pull_deltas() is True

        past = datetime.now(UTC) - timedelta(hours=1)
        alice_old = u_a.save(
            User(
                email="cooldown_alice@example.com",
                password_hash="pw1",
                display_name="Old Alice",
                plan_id=1,
                created_at=past,
            )
        )
        assert alice_old.user_id is not None
        pl_a.save(
            Playlist(
                user_id=alice_old.user_id,
                name="Secret Old Playlist",
                created_at=past + timedelta(minutes=1),
            )
        )
        assert sync_c.pull_deltas(force=True) is True

        # Machine A deletes Alice; verify durable tombstone persistence across restart.
        assert u_a.delete(alice_old.user_id) is True
        tombstone = cloud.get_document(
            "users", user_doc_id("cooldown_alice@example.com")
        )
        assert tombstone is not None and tombstone["is_deleted"] is True
        del_at = tombstone["deleted_at"]
        restarted_sync_a = FirestoreSyncService(conn=conn_a, client=cloud)
        assert "cooldown_alice@example.com" in restarted_sync_a._deleted_user_emails
        assert restarted_sync_a._user_deleted_at["cooldown_alice@example.com"] == del_at

        # Machine B re-registers during pull cooldown without pulling tombstone first.
        reborn_b = u_b.save(
            User(
                email="cooldown_alice@example.com",
                password_hash="pw2",
                display_name="Cooldown Alice",
                plan_id=1,
                created_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        assert reborn_b.user_id is not None
        pl_b.save(
            Playlist(
                user_id=reborn_b.user_id,
                name="Fresh Cooldown Playlist",
                created_at=datetime.now(UTC) + timedelta(seconds=2),
            )
        )
        pushed_doc = cloud.get_document(
            "users", user_doc_id("cooldown_alice@example.com")
        )
        assert pushed_doc is not None
        assert pushed_doc["deleted_at"] == del_at

        # Machine C pulls and purges old Alice & old playlist, keeping reborn Alice & new playlist.
        assert sync_c.pull_deltas(force=True) is True
        alice_c = u_c.find_by_email("cooldown_alice@example.com")
        assert alice_c is not None and alice_c.user_id is not None
        assert alice_c.display_name == "Cooldown Alice"
        assert [p.name for p in pl_c.list_by_user(alice_c.user_id)] == [
            "Fresh Cooldown Playlist"
        ]

        # Partial child delete failure still writes the users tombstone cleanly.
        fail_cloud = _FailingChildDeleteClient("playlists")
        sync_fail = FirestoreSyncService(
            conn=conn_fail,
            client=fail_cloud,  # type: ignore[arg-type]
            min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
        )
        u_fail = SQLiteUserRepository(conn_fail, sync_service=sync_fail)
        pl_fail = SQLitePlaylistRepository(conn_fail, sync_service=sync_fail)
        bob_fail = u_fail.save(
            User(
                email="bob_fail@example.com",
                password_hash="pw",
                display_name="Bob Fail",
                plan_id=1,
                created_at=past,
            )
        )
        assert bob_fail.user_id is not None
        pl_fail.save(Playlist(user_id=bob_fail.user_id, name="Fail Child Playlist"))
        assert u_fail.delete(bob_fail.user_id) is True

        bob_tombstone = fail_cloud.get_document(
            "users", user_doc_id("bob_fail@example.com")
        )
        assert bob_tombstone is not None and bob_tombstone["is_deleted"] is True

        # Inject a stale active pre-deletion user doc; pull must not resurrect it.
        fail_cloud.upsert_document(
            "users",
            "stale-bob-active",
            {
                "email": "bob_fail@example.com",
                "password_hash": "pw",
                "display_name": "Zombie Bob",
                "created_at": past.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "is_deleted": False,
                "updated_at": (datetime.now(UTC) + timedelta(minutes=5)).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            },
        )
        assert sync_fail.pull_deltas(force=True) is True
        assert u_fail.find_by_email("bob_fail@example.com") is None
        assert "bob_fail@example.com" in sync_fail._deleted_user_emails
    finally:
        conn_c.close()
        conn_fail.close()


def test_cooldown_like_does_not_resurrect_deleted_review_and_attempts_do_not_leak(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a,
        client=cloud,
        min_pull_interval_seconds=0.0,  # type: ignore[arg-type]
    )
    sync_b = FirestoreSyncService(
        conn=conn_b,
        client=cloud,
        min_pull_interval_seconds=60.0,  # type: ignore[arg-type]
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    tr_a = SQLiteTrackRepository(conn_a)
    rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    author_a = u_a.save(
        User(
            email="mono_author@example.com",
            password_hash="pw",
            display_name="Author",
            plan_id=1,
        )
    )
    voter_b = u_b.save(
        User(
            email="mono_voter@example.com",
            password_hash="pw",
            display_name="Voter",
            plan_id=1,
        )
    )
    assert author_a.user_id is not None and voter_b.user_id is not None

    track_a = tr_a.save(
        Track(
            title="Monotonic Song",
            artist="Mono Band",
            duration_seconds=200,
            genre="Pop",
            spotify_id="sp_mono_1",
        )
    )
    assert track_a.track_id is not None
    rev = rev_a.save(
        ReviewComment(
            user_id=author_a.user_id,
            track_id=track_a.track_id,
            initial_rating=4,
            text="Soon deleted review",
        )
    )
    assert rev.review_id is not None

    # Machine B caches the review (and starts pull cooldown).
    assert sync_b.pull_deltas(force=True) is True
    track_b = SQLiteTrackRepository(conn_b).find_by_spotify_id("sp_mono_1")
    assert track_b is not None and track_b.track_id is not None
    cached_revs = rev_b.list_by_track(track_b.track_id, limit=10)
    assert len(cached_revs) == 1
    cached_rev_id = cached_revs[0].review_id
    assert cached_rev_id is not None

    # Machine A deletes the review while Machine B is in cooldown.
    assert rev_a.delete(rev.review_id) is True

    # Machine B likes the cached review during cooldown; must neither resurrect remote nor local.
    rev_b.record_like(cached_rev_id, voter_b.user_id)
    rev_docs = cloud.list_documents("reviews")
    assert len(rev_docs) == 1 and rev_docs[0]["is_deleted"] is True
    assert rev_b.list_by_track(track_b.track_id, limit=10) == []

    # Monotonic _apply_review_doc + bounded orphan like cleanup without leaking attempts.
    stale_active = dict(rev_docs[0])
    stale_active["is_deleted"] = False
    stale_active["updated_at"] = "2026-11-15T11:58:00.000000Z"
    cloud.upsert_document("reviews", str(stale_active["_doc_id"]), stale_active)
    assert sync_a.pull_deltas(force=True) is True
    assert rev_a.list_by_track(track_a.track_id, limit=10) == []
    orphan_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cloud.upsert_document(
        "review_likes",
        "leak-check-orphan",
        {
            "review_user_email": "noone_author@example.com",
            "review_created_at": "2026-11-15T11:59:00.000000Z",
            "user_email": "noone_liker@example.com",
            "track_spotify_id": "sp_no_such_track",
            "track_title": "Ghost Track",
            "track_artist": "Ghost Artist",
            "updated_at": orphan_ts,
        },
    )
    for _ in range(3):
        assert sync_b.pull_deltas(force=True) is True
    assert sync_b._pending_review_likes == {}
    assert sync_b._pending_like_attempts == {}
    assert sync_b._watermarks["review_likes"] == orphan_ts


def _ts_utc(offset_seconds: int) -> datetime:
    return datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC) + timedelta(
        seconds=offset_seconds
    )


def _iso_z(offset_seconds: int) -> str:
    return _ts_utc(offset_seconds).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_reborn_user_protected_against_stale_pull_and_offline_sync(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    conn_c = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        sync_a = FirestoreSyncService(
            conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_b = FirestoreSyncService(
            conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
        )
        u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
        u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

        old_user = u_a.save(
            User(
                email="reborn@example.com",
                password_hash="pw1",
                display_name="Old Name",
                plan_id=1,
                created_at=_ts_utc(10),
            )
        )
        assert old_user.user_id is not None
        stale_doc = cloud.get_document("users", user_doc_id("reborn@example.com"))
        assert stale_doc is not None
        stale_doc = dict(stale_doc)

        assert u_a.delete(old_user.user_id) is True
        reborn_user = u_a.save(
            User(
                email="reborn@example.com",
                password_hash="pw2",
                display_name="Reborn Name",
                plan_id=1,
                created_at=datetime.now(UTC) + timedelta(seconds=10),
            )
        )
        assert reborn_user.user_id is not None

        # Path 1: stale active doc or older tombstone pulled onto reborn machine.
        stale_doc["updated_at"] = _iso_z(99999)
        cloud.upsert_document("users", user_doc_id("reborn@example.com"), stale_doc)
        assert sync_a.pull_deltas(force=True) is True
        fetched = u_a.find_by_email("reborn@example.com")
        assert fetched is not None and fetched.display_name == "Reborn Name"

        tomb_doc = {
            "email": "reborn@example.com",
            "is_deleted": True,
            "deleted_at": _iso_z(20),
            "updated_at": _iso_z(999999),
        }
        cloud.upsert_document("users", user_doc_id("reborn@example.com"), tomb_doc)
        assert sync_a.pull_deltas(force=True) is True
        fetched_after_tomb = u_a.find_by_email("reborn@example.com")
        assert fetched_after_tomb is not None
        assert fetched_after_tomb.display_name == "Reborn Name"

        # Path 2: offline registration + sync_all against an older cloud tombstone.
        cloud.upsert_document(
            "users",
            user_doc_id("offline_reborn@example.com"),
            {
                "email": "offline_reborn@example.com",
                "is_deleted": True,
                "deleted_at": _iso_z(30),
                "updated_at": _iso_z(30),
            },
        )
        offline_u_c = SQLiteUserRepository(conn_c, sync_service=None)
        offline_u_c.save(
            User(
                email="offline_reborn@example.com",
                password_hash="pw_c",
                display_name="Offline Reborn",
                plan_id=1,
                created_at=_ts_utc(60),
            )
        )
        sync_c = FirestoreSyncService(
            conn=conn_c, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_c.sync_all()
        remote_off = cloud.get_document(
            "users", user_doc_id("offline_reborn@example.com")
        )
        assert remote_off is not None
        assert remote_off["is_deleted"] is False
        assert remote_off["display_name"] == "Offline Reborn"
        assert u_b.find_by_email("offline_reborn@example.com") is not None
    finally:
        conn_c.close()


def test_reborn_user_protected_against_stale_cooldown_profile_push(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=60.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    t1 = _ts_utc(10)
    t3 = datetime.now(UTC) + timedelta(seconds=10)
    old_a = u_a.save(
        User(
            email="cooldown_reborn@example.com",
            password_hash="pw1",
            display_name="Old B Copy",
            plan_id=1,
            created_at=t1,
        )
    )
    assert old_a.user_id is not None

    cached_b = u_b.find_by_email("cooldown_reborn@example.com")
    assert cached_b is not None and cached_b.user_id is not None

    assert u_a.delete(old_a.user_id) is True
    u_a.save(
        User(
            email="cooldown_reborn@example.com",
            password_hash="pw2",
            display_name="Fresh Reborn",
            plan_id=1,
            created_at=t3,
        )
    )

    cached_b.update_profile(display_name="Stale B Overwrite")
    u_b.save(cached_b)

    remote_doc = cloud.get_document("users", user_doc_id("cooldown_reborn@example.com"))
    assert remote_doc is not None
    assert remote_doc["is_deleted"] is False
    assert remote_doc["display_name"] == "Fresh Reborn"


def test_cooldown_ta_review_like_after_sp_enrichment_and_delete_does_not_resurrect(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    conn_c = _make_memory_db()
    try:
        cloud = _InMemoryFirestoreClient()
        sync_a = FirestoreSyncService(
            conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_b = FirestoreSyncService(
            conn=conn_b, client=cloud, min_pull_interval_seconds=60.0
        )
        u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
        u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
        tr_a = SQLiteTrackRepository(conn_a)
        rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
        rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

        author_a = u_a.save(
            User(
                email="ta_author@example.com",
                password_hash="pw",
                display_name="TA Author",
                plan_id=1,
            )
        )
        voter_b = u_b.save(
            User(
                email="ta_voter@example.com",
                password_hash="pw",
                display_name="TA Voter",
                plan_id=1,
            )
        )
        assert author_a.user_id is not None and voter_b.user_id is not None

        track_a = tr_a.save(
            Track(
                title="Enrich Later",
                artist="Enrich Band",
                duration_seconds=210,
                genre="Rock",
                spotify_id=None,
            )
        )
        track_a2 = tr_a.save(
            Track(
                title="Enrich Later Two",
                artist="Enrich Band Two",
                duration_seconds=200,
                genre="Pop",
                spotify_id=None,
            )
        )
        assert track_a.track_id is not None and track_a2.track_id is not None
        rev = rev_a.save(
            ReviewComment(
                user_id=author_a.user_id,
                track_id=track_a.track_id,
                initial_rating=5,
                text="Initial ta review",
            )
        )
        rev2 = rev_a.save(
            ReviewComment(
                user_id=author_a.user_id,
                track_id=track_a2.track_id,
                initial_rating=4,
                text="Initial ta review 2",
            )
        )
        assert rev.review_id is not None and rev2.review_id is not None

        assert sync_b.pull_deltas(force=True) is True
        track_b = SQLiteTrackRepository(conn_b).find_by_title_and_artist(
            "Enrich Later", "Enrich Band"
        )
        track_b2 = SQLiteTrackRepository(conn_b).find_by_title_and_artist(
            "Enrich Later Two", "Enrich Band Two"
        )
        assert track_b is not None and track_b.track_id is not None
        assert track_b2 is not None and track_b2.track_id is not None
        assert track_b.spotify_id is None and track_b2.spotify_id is None
        cached_revs = rev_b.list_by_track(track_b.track_id, limit=10)
        cached_revs2 = rev_b.list_by_track(track_b2.track_id, limit=10)
        assert len(cached_revs) == 1 and cached_revs[0].review_id is not None
        assert len(cached_revs2) == 1 and cached_revs2[0].review_id is not None

        tr_a.save(
            Track(
                track_id=track_a.track_id,
                title="Enrich Later",
                artist="Enrich Band",
                duration_seconds=210,
                genre="Rock",
                spotify_id="sp_enriched_late_1",
            )
        )
        tr_a.save(
            Track(
                track_id=track_a2.track_id,
                title="Enrich Later Two",
                artist="Enrich Band Two",
                duration_seconds=200,
                genre="Pop",
                spotify_id="sp_enriched_late_2",
            )
        )
        assert rev_a.delete(rev.review_id) is True
        assert rev_a.delete(rev2.review_id) is True

        # Machine B (still un-enriched & in cooldown) likes one and saves the other.
        rev_b.record_like(cached_revs[0].review_id, voter_b.user_id)
        rev_b.save(cached_revs2[0].update_content(3, "Cooldown edited text"))

        rev_docs = cloud.list_documents("reviews")
        assert len(rev_docs) == 2
        assert all(d["is_deleted"] is True for d in rev_docs)
        assert rev_b.list_by_track(track_b.track_id, limit=10) == []
        assert rev_b.list_by_track(track_b2.track_id, limit=10) == []

        # Also inject a stale active ta_* doc with a newer updated_at; dedup on fresh 3rd peer
        # (and pre-seeded track_d) must prefer deletion.
        ta_key = track_sync_key(None, "Enrich Later", "Enrich Band")
        ta_doc_id = review_doc_id(
            "ta_author@example.com", ta_key, str(rev_docs[0]["created_at"])
        )
        stale_ta = dict(rev_docs[0])
        stale_ta["is_deleted"] = False
        stale_ta["track_spotify_id"] = None
        stale_ta["sync_key"] = ta_doc_id
        stale_ta["updated_at"] = (datetime.now(UTC) + timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        cloud.upsert_document("reviews", ta_doc_id, stale_ta)

        sync_c = FirestoreSyncService(
            conn=conn_c, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_c.sync_all()
        active_c = conn_c.execute(
            "SELECT COUNT(*) FROM reviews WHERE is_deleted = 0"
        ).fetchone()
        assert active_c is not None and int(active_c[0]) == 0
    finally:
        conn_c.close()


def test_use_cases_pull_deltas_on_find_by_id_list_dependents_and_active_review(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    tr_a = SQLiteTrackRepository(conn_a)
    tr_b = SQLiteTrackRepository(conn_b)
    rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    primary_a = u_a.save(
        User(
            email="uc_pri@example.com",
            password_hash="pw",
            display_name="Before Edit",
            plan_id=3,
        )
    )
    assert primary_a.user_id is not None
    primary_b = u_b.find_by_email("uc_pri@example.com")
    assert primary_b is not None and primary_b.user_id is not None

    primary_a.update_profile(display_name="After Remote Edit")
    u_a.save(primary_a)
    u_a.save(
        User(
            email="uc_kid@example.com",
            password_hash="pw",
            display_name="Remote Kid",
            plan_id=3,
            primary_account_id=primary_a.user_id,
        )
    )

    profile = GetUserProfileUseCase(u_b, SQLitePlanRepository(conn_b)).execute(
        primary_b.user_id
    )
    assert profile.user.display_name == "After Remote Edit"

    deps = ListFamilyMembersUseCase(u_b).execute(primary_b.user_id)
    assert [d.email for d in deps] == ["uc_kid@example.com"]

    track_a = tr_a.save(
        Track(
            title="UC Dup Track",
            artist="UC Artist",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_uc_dup",
        )
    )
    track_b = tr_b.save(
        Track(
            title="UC Dup Track",
            artist="UC Artist",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_uc_dup",
        )
    )
    assert track_a.track_id is not None and track_b.track_id is not None

    rev_a.save(
        ReviewComment(
            user_id=primary_a.user_id,
            track_id=track_a.track_id,
            initial_rating=4,
            text="Remote review",
        )
    )
    with pytest.raises(DuplicateEntityError):
        PublishReviewUseCase(u_b, tr_b, rev_b).execute(
            PublishReviewCommand(
                user_id=primary_b.user_id,
                track_id=track_b.track_id,
                rating=5,
                text="Should collide",
            )
        )


def test_transient_get_document_error_aborts_push_without_overwriting_remote(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=60.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    tr_a = SQLiteTrackRepository(conn_a)
    rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    user_a = u_a.save(
        User(
            email="err_guard@example.com",
            password_hash="pw",
            display_name="Original",
            plan_id=1,
        )
    )
    rev_author_a = u_a.save(
        User(
            email="err_rev_author@example.com",
            password_hash="pw",
            display_name="Review Author",
            plan_id=1,
        )
    )
    assert user_a.user_id is not None and rev_author_a.user_id is not None
    track_a = tr_a.save(
        Track(
            title="Guard Song",
            artist="Guard Band",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_err_guard",
        )
    )
    assert track_a.track_id is not None
    rev = rev_a.save(
        ReviewComment(
            user_id=rev_author_a.user_id,
            track_id=track_a.track_id,
            initial_rating=4,
            text="To be deleted",
        )
    )
    assert rev.review_id is not None

    assert sync_b.pull_deltas(force=True) is True
    user_b = u_b.find_by_email("err_guard@example.com")
    track_b = SQLiteTrackRepository(conn_b).find_by_spotify_id("sp_err_guard")
    assert user_b is not None and user_b.user_id is not None
    assert track_b is not None and track_b.track_id is not None
    rev_b_rows = rev_b.list_by_track(track_b.track_id, limit=10)
    assert len(rev_b_rows) == 1 and rev_b_rows[0].review_id is not None

    assert u_a.delete(user_a.user_id) is True
    assert rev_a.delete(rev.review_id) is True

    def _boom(_collection: str, _doc_id: str) -> dict[str, Any] | None:
        raise ExternalServiceError("Firestore", "503 transient failure")

    monkeypatch.setattr(cloud, "get_document", _boom)

    sync_b.push_user_by_id(user_b.user_id)
    sync_b.push_review_by_id(rev_b_rows[0].review_id)

    monkeypatch.undo()
    remote_user = cloud.get_document("users", user_doc_id("err_guard@example.com"))
    assert remote_user is not None and remote_user["is_deleted"] is True
    remote_revs = cloud.list_documents("reviews")
    assert len(remote_revs) == 1 and remote_revs[0]["is_deleted"] is True


def test_offline_user_deletion_tombstone_pushed_on_sync_all_reconnect(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    user_a = u_a.save(
        User(
            email="offline_del@example.com",
            password_hash="pw",
            display_name="Offline Del",
            plan_id=1,
        )
    )
    assert user_a.user_id is not None
    assert u_b.find_by_email("offline_del@example.com") is not None

    def _offline_upsert(
        _collection: str, _doc_id: str, _data: Mapping[str, Any]
    ) -> None:
        raise ExternalServiceError("Firestore", "offline")

    monkeypatch.setattr(cloud, "upsert_document", _offline_upsert)
    assert u_a.delete(user_a.user_id) is True

    monkeypatch.undo()
    before_reconnect = cloud.get_document(
        "users", user_doc_id("offline_del@example.com")
    )
    assert before_reconnect is not None and before_reconnect["is_deleted"] is False

    sync_a.sync_all()
    after_reconnect = cloud.get_document(
        "users", user_doc_id("offline_del@example.com")
    )
    assert after_reconnect is not None and after_reconnect["is_deleted"] is True
    assert u_b.find_by_email("offline_del@example.com") is None


def test_exhausted_orphan_review_likes_stay_ignored_across_six_pulls(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, _conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    recent_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cloud.upsert_document(
        "review_likes",
        "orphan-loop-check",
        {
            "review_user_email": "missing_author@example.com",
            "review_created_at": "2026-11-15T11:00:00.000000Z",
            "user_email": "missing_voter@example.com",
            "track_spotify_id": "sp_missing_track",
            "track_title": "Missing Track",
            "track_artist": "Missing Artist",
            "updated_at": recent_ts,
        },
    )
    for _ in range(7):
        assert sync_a.pull_deltas(force=True) is True
    assert sync_a._pending_review_likes == {}
    assert sync_a._pending_like_attempts == {}
    assert sync_a._exhausted_review_likes == {"orphan-loop-check": recent_ts}
    assert sync_a._watermarks["review_likes"] == recent_ts


def test_unlinked_dependent_not_relinked_when_primary_reregisters(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=60.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    # Path 1: DeleteUserAccountUseCase + cooldown dependent save + primary re-registration.
    pri_1 = u_a.save(
        User(
            email="unlink_pri1@example.com",
            password_hash="pw",
            display_name="Pri 1",
            plan_id=3,
        )
    )
    assert pri_1.user_id is not None
    u_a.save(
        User(
            email="unlink_dep1@example.com",
            password_hash="pw",
            display_name="Dep 1",
            plan_id=3,
            primary_account_id=pri_1.user_id,
        )
    )
    assert sync_b.pull_deltas(force=True) is True
    dep1_b = u_b.find_by_email("unlink_dep1@example.com")
    assert dep1_b is not None and dep1_b.primary_account_id is not None

    DeleteUserAccountUseCase(u_a, SQLitePlanRepository(conn_a)).execute(pri_1.user_id)
    dep1_b.update_profile(display_name="Dep 1 Edited Cooldown")
    u_b.save(dep1_b)
    u_a.save(
        User(
            email="unlink_pri1@example.com",
            password_hash="pw_new",
            display_name="Pri 1 Reborn",
            plan_id=3,
            created_at=datetime.now(UTC) + timedelta(seconds=10),
        )
    )
    assert sync_b.pull_deltas(force=True) is True
    dep1_after_b = u_b.find_by_email("unlink_dep1@example.com")
    assert dep1_after_b is not None and dep1_after_b.primary_account_id is None

    # Path 2: direct user_repo.delete + primary re-registration.
    pri_2 = u_a.save(
        User(
            email="unlink_pri2@example.com",
            password_hash="pw",
            display_name="Pri 2",
            plan_id=3,
        )
    )
    assert pri_2.user_id is not None
    u_a.save(
        User(
            email="unlink_dep2@example.com",
            password_hash="pw",
            display_name="Dep 2",
            plan_id=3,
            primary_account_id=pri_2.user_id,
        )
    )
    assert sync_b.pull_deltas(force=True) is True
    assert u_a.delete(pri_2.user_id) is True
    dep2_doc = cloud.get_document("users", user_doc_id("unlink_dep2@example.com"))
    assert dep2_doc is not None and dep2_doc["primary_user_email"] is None

    u_a.save(
        User(
            email="unlink_pri2@example.com",
            password_hash="pw_new2",
            display_name="Pri 2 Reborn",
            plan_id=3,
            created_at=datetime.now(UTC) + timedelta(seconds=20),
        )
    )
    assert sync_b.pull_deltas(force=True) is True
    dep2_after_b = u_b.find_by_email("unlink_dep2@example.com")
    assert dep2_after_b is not None and dep2_after_b.primary_account_id is None


def test_failed_apply_user_doc_savepoint_rollback_preserves_tombstone_state(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    tomb_user = u_a.save(
        User(
            email="tomb_victim@example.com",
            password_hash="pw",
            display_name="Victim",
            plan_id=1,
            created_at=_ts_utc(5),
        )
    )
    assert tomb_user.user_id is not None
    assert u_a.delete(tomb_user.user_id) is True
    assert u_b.find_by_email("tomb_victim@example.com") is None
    assert "tomb_victim@example.com" in sync_b._deleted_user_emails

    # Reborn doc will fail mid-_upsert_local_user and trigger ROLLBACK TO SAVEPOINT.
    reborn_doc = {
        "email": "tomb_victim@example.com",
        "password_hash": "pw2",
        "display_name": "Should Rollback",
        "plan_id": 1,
        "is_deleted": False,
        "created_at": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        "deleted_at": _iso_z(20),
        "updated_at": _iso_z(999999),
    }
    cloud.upsert_document("users", user_doc_id("tomb_victim@example.com"), reborn_doc)

    def _boom_upsert(
        _cursor: sqlite3.Cursor,
        _existing: sqlite3.Row | None,
        _email: str,
        _doc: Mapping[str, Any],
        _fields: tuple[Any, ...],
    ) -> None:
        raise RuntimeError("Simulated SQL failure")

    monkeypatch.setattr(sync_b, "_upsert_local_user", _boom_upsert)
    assert sync_b.pull_deltas(force=True) is True

    db_row = conn_b.execute(
        "SELECT deleted_at, is_deleted FROM _firestore_user_tombstones WHERE email = ?",
        ("tomb_victim@example.com",),
    ).fetchone()
    assert db_row is not None and db_row["is_deleted"] == 1
    assert "tomb_victim@example.com" in sync_b._deleted_user_emails
    assert sync_b._user_deleted_at["tomb_victim@example.com"] == db_row["deleted_at"]


class _ToggleClient(_InMemoryFirestoreClient):
    """Test Firestore client wrapper that toggles offline ExternalServiceError."""

    def __init__(self, backing: _InMemoryFirestoreClient) -> None:
        super().__init__()
        self._backing = backing
        self.online = True

    def _require_online(self) -> None:
        if not self.online:
            raise ExternalServiceError("offline", service_name="GCP_Firestore")

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        self._require_online()
        return self._backing.get_document(collection, doc_id)

    def upsert_document(
        self, collection: str, doc_id: str, data: Mapping[str, Any]
    ) -> None:
        self._require_online()
        self._backing.upsert_document(collection, doc_id, data)

    def delete_document(self, collection: str, doc_id: str) -> None:
        self._require_online()
        self._backing.delete_document(collection, doc_id)

    def list_documents(self, collection: str) -> list[dict[str, Any]]:
        self._require_online()
        return self._backing.list_documents(collection)

    def query_updated_since(
        self, collection: str, since_iso: str | None = None
    ) -> list[dict[str, Any]]:
        self._require_online()
        return self._backing.query_updated_since(collection, since_iso)


def test_reverse_ta_deletion_blocks_sp_cooldown_like_and_edit(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=60.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    tr_a = SQLiteTrackRepository(conn_a)
    tr_b = SQLiteTrackRepository(conn_b)
    rev_a = SQLiteReviewRepository(conn_a, sync_service=sync_a)
    rev_b = SQLiteReviewRepository(conn_b, sync_service=sync_b)

    voter_a = u_a.save(
        User(
            email="rev_voter_a@example.com",
            password_hash="pw",
            display_name="Voter A",
            plan_id=1,
        )
    )
    author_b = u_b.save(
        User(
            email="rev_author_b@example.com",
            password_hash="pw",
            display_name="Author B",
            plan_id=1,
        )
    )
    track_a1 = tr_a.save(
        Track(
            title="Reverse Mono One",
            artist="Reverse Band 1",
            duration_seconds=200,
            genre="Rock",
            spotify_id="sp_rev_mono_1",
        )
    )
    track_a2 = tr_a.save(
        Track(
            title="Reverse Mono Two",
            artist="Reverse Band 2",
            duration_seconds=210,
            genre="Pop",
            spotify_id="sp_rev_mono_2",
        )
    )
    track_b1 = tr_b.save(
        Track(
            title="Reverse Mono One",
            artist="Reverse Band 1",
            duration_seconds=200,
            genre="Rock",
            spotify_id=None,
        )
    )
    track_b2 = tr_b.save(
        Track(
            title="Reverse Mono Two",
            artist="Reverse Band 2",
            duration_seconds=210,
            genre="Pop",
            spotify_id=None,
        )
    )
    assert (
        voter_a.user_id is not None
        and author_b.user_id is not None
        and track_a1.track_id is not None
        and track_a2.track_id is not None
        and track_b1.track_id is not None
        and track_b2.track_id is not None
    )

    rev_b1 = rev_b.save(
        ReviewComment(
            user_id=author_b.user_id,
            track_id=track_b1.track_id,
            initial_rating=5,
            text="B review 1",
        )
    )
    rev_b2 = rev_b.save(
        ReviewComment(
            user_id=author_b.user_id,
            track_id=track_b2.track_id,
            initial_rating=4,
            text="B review 2",
        )
    )
    assert rev_b1.review_id is not None and rev_b2.review_id is not None

    # Machine A pulls into its enriched sp_* tracks and enters pull cooldown.
    assert sync_a.pull_deltas(force=True) is True
    cached_a1 = rev_a.list_by_track(track_a1.track_id, limit=10)
    cached_a2 = rev_a.list_by_track(track_a2.track_id, limit=10)
    assert len(cached_a1) == 1 and cached_a1[0].review_id is not None
    assert len(cached_a2) == 1 and cached_a2[0].review_id is not None

    # Machine B deletes both ta_* reviews cleanly.
    assert rev_b.delete(rev_b1.review_id) is True
    assert rev_b.delete(rev_b2.review_id) is True

    # Machine A (sp_*, in cooldown) attempts like + edit; neither resurrects or leaves orphans.
    rev_a.record_like(cached_a1[0].review_id, voter_a.user_id)
    rev_a.save(cached_a2[0].update_content(2, "Cooldown sp edit should vanish"))

    assert cloud.list_documents("review_likes") == []
    like_count_a = conn_a.execute("SELECT COUNT(*) FROM review_likes").fetchone()
    assert like_count_a is not None and int(like_count_a[0]) == 0
    rev_docs = cloud.list_documents("reviews")
    assert len(rev_docs) == 2
    assert all(d["is_deleted"] is True for d in rev_docs)
    assert rev_a.list_by_track(track_a1.track_id, limit=10) == []
    assert rev_a.list_by_track(track_a2.track_id, limit=10) == []


def test_secondary_seed_sync_all_does_not_overwrite_customized_cloud_admin() -> None:
    cloud = _InMemoryFirestoreClient()
    settings = Settings(
        admin_email="admin_seed_sync@example.com",
        admin_password="InitialSeedPassword1!",  # noqa: S106
        admin_eligible_emails=("admin_seed_sync@example.com",),
        password_hash_iterations=10_000,
    )
    conn_a = _make_memory_db()
    conn_b = _make_memory_db()
    try:
        seed_database(conn_a, settings=settings)
        seeded_row = conn_a.execute(
            "SELECT created_at FROM users WHERE email = ?",
            ("admin_seed_sync@example.com",),
        ).fetchone()
        assert (
            seeded_row is not None
            and seeded_row["created_at"] == "1970-01-01T00:00:00+00:00"
        )

        sync_a = FirestoreSyncService(
            conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_a.sync_all()

        u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
        admin_a = u_a.find_by_email("admin_seed_sync@example.com")
        assert admin_a is not None and admin_a.user_id is not None
        u_a.save(
            User(
                user_id=admin_a.user_id,
                email=admin_a.email,
                password_hash="custom_admin_pw_hash_v2",
                display_name="Customized Cloud Admin",
                plan_id=admin_a.plan_id,
                is_admin=True,
                created_at=admin_a.created_at,
            )
        )
        promoted = conn_a.execute(
            "SELECT created_at FROM users WHERE user_id = ?", (admin_a.user_id,)
        ).fetchone()
        assert (
            promoted is not None
            and promoted["created_at"] != "1970-01-01T00:00:00+00:00"
        )

        # Fresh secondary node boots with seed_database then sync_all().
        seed_database(conn_b, settings=settings)
        sync_b = FirestoreSyncService(
            conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
        )
        sync_b.sync_all()

        admin_b = SQLiteUserRepository(conn_b).find_by_email(
            "admin_seed_sync@example.com"
        )
        assert admin_b is not None
        assert admin_b.display_name == "Customized Cloud Admin"
        assert admin_b.password_hash == "custom_admin_pw_hash_v2"
        cloud_admin = cloud.get_document(
            "users", user_doc_id("admin_seed_sync@example.com")
        )
        assert cloud_admin is not None
        assert cloud_admin["display_name"] == "Customized Cloud Admin"
        assert cloud_admin["password_hash"] == "custom_admin_pw_hash_v2"
    finally:
        conn_a.close()
        conn_b.close()


def test_offline_primary_delete_then_dependent_edit_then_reborn_keeps_dependent_unlinked(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    client_a = _ToggleClient(cloud)
    now_dt = datetime.now(UTC)
    t0_dt = now_dt - timedelta(seconds=300)
    ts_box = [(now_dt - timedelta(seconds=290)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")]
    monkeypatch.setattr(
        "app.infrastructure.adapters.gcp.firestore_sync._utc_now_iso",
        lambda: ts_box[0],
    )

    sync_a = FirestoreSyncService(
        conn=conn_a, client=client_a, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    pri_a = u_a.save(
        User(
            email="off_pri@example.com",
            password_hash="pw",
            display_name="Pri",
            plan_id=3,
            created_at=t0_dt,
        )
    )
    assert pri_a.user_id is not None
    u_a.save(
        User(
            email="off_dep@example.com",
            password_hash="pw",
            display_name="Dep",
            plan_id=3,
            primary_account_id=pri_a.user_id,
            created_at=t0_dt + timedelta(seconds=1),
        )
    )
    assert sync_b.pull_deltas(force=True) is True
    dep_b = u_b.find_by_email("off_dep@example.com")
    assert dep_b is not None and dep_b.primary_account_id is not None

    # T_del: Machine A deletes primary while offline.
    client_a.online = False
    ts_box[0] = (now_dt - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    DeleteUserAccountUseCase(u_a, SQLitePlanRepository(conn_a)).execute(pri_a.user_id)

    # T_edit > T_del: Machine B edits dependent online while stale primary is still in Cloud.
    ts_box[0] = (now_dt - timedelta(seconds=100)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    dep_b.update_profile(display_name="Dep Edited While Offline Delete")
    u_b.save(dep_b)

    # T_reborn > T_edit: Machine A re-registers primary email while still offline.
    t_reborn_dt = now_dt - timedelta(seconds=10)
    ts_box[0] = t_reborn_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    u_a.save(
        User(
            email="off_pri@example.com",
            password_hash="pw_reborn",
            display_name="Pri Reborn",
            plan_id=3,
            created_at=t_reborn_dt,
        )
    )

    # Reconnect Machine A and propagate both sides.
    client_a.online = True
    ts_box[0] = now_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    sync_a.sync_all()
    assert sync_b.pull_deltas(force=True) is True

    free_plan = SQLitePlanRepository(conn_b).find_by_name("Free")
    assert free_plan is not None and free_plan.plan_id is not None
    dep_after_a = u_a.find_by_email("off_dep@example.com")
    dep_after_b = u_b.find_by_email("off_dep@example.com")
    assert dep_after_a is not None
    assert dep_after_a.primary_account_id is None
    assert dep_after_a.plan_id == free_plan.plan_id
    assert dep_after_b is not None
    assert dep_after_b.primary_account_id is None
    assert dep_after_b.plan_id == free_plan.plan_id
    cloud_dep = cloud.get_document("users", user_doc_id("off_dep@example.com"))
    assert cloud_dep is not None
    assert cloud_dep["primary_user_email"] is None
    assert cloud_dep["plan_id"] == free_plan.plan_id
    assert cloud_dep["plan_name"] == "Free"


def test_playlist_cooldown_mutations_do_not_resurrect_and_offline_delete_syncs(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    client_b = _ToggleClient(cloud)
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=60.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=client_b, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    tr_a = SQLiteTrackRepository(conn_a)
    pl_repo_a = SQLitePlaylistRepository(conn_a, sync_service=sync_a)
    pl_repo_b = SQLitePlaylistRepository(conn_b, sync_service=sync_b)

    owner_a = u_a.save(
        User(
            email="pl_guard@example.com",
            password_hash="pw",
            display_name="PL Guard",
            plan_id=1,
        )
    )
    t1 = tr_a.save(
        Track(
            title="PL Song 1",
            artist="PL Artist 1",
            duration_seconds=180,
            genre="Pop",
            spotify_id="sp_pl_guard_1",
        )
    )
    t2 = tr_a.save(
        Track(
            title="PL Song 2",
            artist="PL Artist 2",
            duration_seconds=190,
            genre="Pop",
            spotify_id="sp_pl_guard_2",
        )
    )
    assert (
        owner_a.user_id is not None
        and t1.track_id is not None
        and t2.track_id is not None
    )
    base_dt = datetime.now(UTC) - timedelta(seconds=30)
    pl_save_a = pl_repo_a.save(
        Playlist(
            user_id=owner_a.user_id,
            name="Guard Save",
            description="desc",
            created_at=base_dt,
        )
    )
    pl_img_a = pl_repo_a.save(
        Playlist(
            user_id=owner_a.user_id,
            name="Guard Img",
            description="desc",
            created_at=base_dt + timedelta(seconds=1),
        )
    )
    pl_rem_a = pl_repo_a.save(
        Playlist(
            user_id=owner_a.user_id,
            name="Guard Rem",
            description="desc",
            initial_tracks=[t1, t2],
            created_at=base_dt + timedelta(seconds=2),
        )
    )
    assert (
        pl_save_a.playlist_id is not None
        and pl_img_a.playlist_id is not None
        and pl_rem_a.playlist_id is not None
    )
    assert sync_a.pull_deltas(force=True) is True

    owner_b = SQLiteUserRepository(conn_b, sync_service=sync_b).find_by_email(
        "pl_guard@example.com"
    )
    assert owner_b is not None and owner_b.user_id is not None
    for pl_b in pl_repo_b.list_by_user(owner_b.user_id):
        assert pl_b.playlist_id is not None
        assert pl_repo_b.delete(pl_b.playlist_id) is True

    pt_before = [dict(d) for d in cloud.list_documents("playlist_tracks")]

    # Machine A (in cooldown) attempts save, save_cover_image, and remove_track separately.
    pl_save_a.name = "Resurrected In Cooldown"
    pl_repo_a.save(pl_save_a)
    pl_repo_a.save_cover_image(
        pl_img_a.playlist_id,
        "image/png",
        b"\x89PNG-cooldown-guard",
        f"/api/playlists/{pl_img_a.playlist_id}/image",
    )
    pl_repo_a.remove_track(pl_rem_a.playlist_id, t1.track_id)

    pl_docs = cloud.list_documents("playlists")
    assert len(pl_docs) == 3 and all(d["is_deleted"] is True for d in pl_docs)
    assert cloud.list_documents("playlist_images") == []
    assert cloud.list_documents("playlist_tracks") == pt_before
    assert pl_repo_a.find_by_id(pl_save_a.playlist_id) is None
    assert pl_repo_a.find_by_id(pl_img_a.playlist_id) is None
    assert pl_repo_a.find_by_id(pl_rem_a.playlist_id) is None

    # Offline playlist deletion queues tombstone and pushes upon reconnect sync_all().
    pl2_b = pl_repo_b.save(
        Playlist(
            user_id=owner_b.user_id,
            name="Offline Delete PL",
            description="off",
            created_at=base_dt + timedelta(seconds=3),
        )
    )
    assert pl2_b.playlist_id is not None
    client_b.online = False
    assert pl_repo_b.delete(pl2_b.playlist_id) is True
    client_b.online = True
    sync_b.sync_all()

    docs_after = {
        d["name"]: d for d in cloud.list_documents("playlists") if "name" in d
    }
    assert "Offline Delete PL" not in docs_after
    deleted_docs = [
        d for d in cloud.list_documents("playlists") if d.get("is_deleted") is True
    ]
    assert len(deleted_docs) == 4


def test_exhausted_orphan_review_like_recovers_when_parent_arrives(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    sync_a = FirestoreSyncService(
        conn=conn_a, client=cloud, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)
    u_b.save(
        User(
            email="author_rec@example.com",
            password_hash="pw",
            display_name="Author Rec",
            plan_id=1,
        )
    )
    u_b.save(
        User(
            email="liker_rec@example.com",
            password_hash="pw",
            display_name="Liker Rec",
            plan_id=1,
        )
    )

    now_dt = datetime.now(UTC)
    rev_created_at = (now_dt - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    orphan_like_ts = (now_dt - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    parent_rev_ts = (now_dt - timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    cloud.upsert_document(
        "review_likes",
        "orphan-like-recover-1",
        {
            "review_user_email": "author_rec@example.com",
            "review_created_at": rev_created_at,
            "user_email": "liker_rec@example.com",
            "track_spotify_id": "sp_rec_1",
            "track_title": "Recover Track",
            "track_artist": "Recover Artist",
            "updated_at": orphan_like_ts,
        },
    )

    for _ in range(3):
        assert sync_a.pull_deltas(force=True) is True
    assert sync_a._pending_review_likes == {}
    assert len(sync_a._exhausted_review_likes) == 1
    assert sync_a._watermarks["review_likes"] == orphan_like_ts

    cloud.upsert_document(
        "reviews",
        "parent-rev-recover-1",
        {
            "user_email": "author_rec@example.com",
            "author_name": "Author Rec",
            "rating": 5,
            "text": "Parent review arrived on pull 4",
            "likes_count": 0,
            "is_deleted": False,
            "created_at": rev_created_at,
            "updated_at": parent_rev_ts,
            "track_spotify_id": "sp_rec_1",
            "track_title": "Recover Track",
            "track_artist": "Recover Artist",
            "track_duration_seconds": 180,
            "track_genre": "Pop",
        },
    )
    assert sync_a.pull_deltas(force=True) is True

    reviews_a = SQLiteReviewRepository(conn_a).list_top_recent(days=30, limit=10)
    assert len(reviews_a) == 1
    assert reviews_a[0].likes_count == 1
    liker_a = SQLiteUserRepository(conn_a).find_by_email("liker_rec@example.com")
    assert liker_a is not None and liker_a.user_id is not None
    assert reviews_a[0].review_id is not None
    assert SQLiteReviewRepository(conn_a).has_user_liked(
        reviews_a[0].review_id, liker_a.user_id
    )
    assert sync_a._exhausted_review_likes == {}
    assert sync_a._pending_review_likes == {}


def test_push_pending_user_tombstones_preserves_newer_remote_deleted_at(
    two_machines: tuple[sqlite3.Connection, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn_a, conn_b = two_machines
    cloud = _InMemoryFirestoreClient()
    client_a = _ToggleClient(cloud)
    now_dt = datetime.now(UTC)
    t1_dt = now_dt - timedelta(seconds=200)
    t2_del = (now_dt - timedelta(seconds=150)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    t3_dt = now_dt - timedelta(seconds=100)
    t4_del = (now_dt - timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    ts_box = [(now_dt - timedelta(seconds=190)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")]
    monkeypatch.setattr(
        "app.infrastructure.adapters.gcp.firestore_sync._utc_now_iso",
        lambda: ts_box[0],
    )

    sync_a = FirestoreSyncService(
        conn=conn_a, client=client_a, min_pull_interval_seconds=0.0
    )
    sync_b = FirestoreSyncService(
        conn=conn_b, client=cloud, min_pull_interval_seconds=0.0
    )
    u_a = SQLiteUserRepository(conn_a, sync_service=sync_a)
    u_b = SQLiteUserRepository(conn_b, sync_service=sync_b)

    victim_a = u_a.save(
        User(
            email="tomb_mono@example.com",
            password_hash="pw",
            display_name="Victim",
            plan_id=1,
            created_at=t1_dt,
        )
    )
    assert victim_a.user_id is not None
    assert sync_b.pull_deltas(force=True) is True
    victim_b = u_b.find_by_email("tomb_mono@example.com")
    assert victim_b is not None and victim_b.user_id is not None

    # Machine A deletes offline at T2.
    client_a.online = False
    ts_box[0] = t2_del
    assert u_a.delete(victim_a.user_id) is True

    # Machine B deletes, re-registers at T3, and deletes again at T4 > T2.
    assert u_b.delete(victim_b.user_id) is True
    ts_box[0] = t3_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    victim_b_reborn = u_b.save(
        User(
            email="tomb_mono@example.com",
            password_hash="pw2",
            display_name="Victim Reborn",
            plan_id=1,
            created_at=t3_dt,
        )
    )
    assert victim_b_reborn.user_id is not None
    ts_box[0] = t4_del
    assert u_b.delete(victim_b_reborn.user_id) is True

    # Machine A reconnects and flushes pending tombstones without downgrading T4 to T2.
    client_a.online = True
    ts_box[0] = (now_dt - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    sync_a._push_pending_user_tombstones()

    cloud_doc = cloud.get_document("users", user_doc_id("tomb_mono@example.com"))
    assert cloud_doc is not None and cloud_doc["is_deleted"] is True
    assert cloud_doc["deleted_at"] == t4_del
    tomb_row = conn_a.execute(
        "SELECT deleted_at, is_deleted FROM _firestore_user_tombstones WHERE email = ?",
        ("tomb_mono@example.com",),
    ).fetchone()
    assert tomb_row is not None
    assert tomb_row["is_deleted"] == 1
    assert tomb_row["deleted_at"] == t4_del
    assert sync_a._user_deleted_at["tomb_mono@example.com"] == t4_del
