"""Tests for deployment-only Firestore synchronization."""

import sqlite3
from typing import Any

import pytest

from app.config import Settings
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.gcp.firestore_sync import (
    FirestoreSyncService,
    _iso_lookback,
    _normalize_local_cover_url,
    _parse_iso_utc,
    _pending_like_key,
    _track_key_from_doc,
    _track_sync_keys_for_row,
    playlist_doc_id,
    review_doc_id,
    track_sync_key,
    user_doc_id,
)
from app.infrastructure.repositories.audit_log_repository import (
    SQLiteAuditLogRepository,
)
from app.infrastructure.repositories.connection import SCHEMA_PATH, transaction
from app.infrastructure.repositories.seed import seed_database


class InMemoryFirestoreClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, dict[str, Any]]] = {}

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        return self.documents.get(collection, {}).get(doc_id)

    def upsert_document(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> None:
        self.documents.setdefault(collection, {})[doc_id] = dict(data)

    def delete_document(self, collection: str, doc_id: str) -> None:
        self.documents.get(collection, {}).pop(doc_id, None)

    def query_updated_since(
        self, collection: str, since_iso: str | None = None
    ) -> list[dict[str, Any]]:
        documents = [
            {**document, "_doc_id": doc_id}
            for doc_id, document in self.documents.get(collection, {}).items()
        ]
        if since_iso is None:
            return documents
        return [
            document
            for document in documents
            if str(document.get("updated_at") or "") > since_iso
        ]

    def list_documents(self, collection: str) -> list[dict[str, Any]]:
        return [
            {**document, "_doc_id": doc_id}
            for doc_id, document in self.documents.get(collection, {}).items()
        ]


def _seeded_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    seed_database(
        conn,
        settings=Settings(database_path=":memory:", password_hash_iterations=1_000),
    )
    return conn


def test_firestore_sync_keys_dates_deduplication_and_cover_normalization() -> None:
    assert user_doc_id(" USER@example.com ") == user_doc_id("user@example.com")
    assert track_sync_key("spotify:track/1", "Song", "Artist") == "sp_spotify_track_1"
    assert track_sync_key(None, " Song ", " Artist ") == track_sync_key(
        None, "song", "artist"
    )
    assert review_doc_id("USER@example.com", "track", " now ") == review_doc_id(
        "user@example.com", "track", "now"
    )
    assert playlist_doc_id("USER@example.com", " now ") == playlist_doc_id(
        "user@example.com", "now"
    )
    assert (
        _track_key_from_doc(
            {"track_spotify_id": "id", "track_title": "Song", "track_artist": "Artist"}
        )
        == "sp_id"
    )
    assert _track_sync_keys_for_row(
        {
            "track_spotify_id": "id",
            "track_title": "Song",
            "track_artist": "Artist",
        }
    ) == ("sp_id", track_sync_key(None, "Song", "Artist"))
    assert _parse_iso_utc("2026-01-01T00:00:00") is not None
    assert _parse_iso_utc("invalid") is None
    assert _parse_iso_utc(None) is None
    assert _iso_lookback("invalid") == "invalid"
    assert _iso_lookback("2026-01-01T00:01:00+00:00").startswith("2026-01-01T00:00:00")
    assert (
        _pending_like_key(
            {
                "review_user_email": " AUTHOR@example.com ",
                "user_email": " LIKER@example.com ",
                "review_created_at": " today ",
            }
        )
        == "author@example.com::liker@example.com::today"
    )
    assert _pending_like_key({"_doc_id": " like-id "}) == "like-id"
    assert _normalize_local_cover_url("/api/playlists/8/image", 42) == (
        "/api/playlists/42/image"
    )
    assert _normalize_local_cover_url("https://example.test/cover", 42) == (
        "https://example.test/cover"
    )
    assert _normalize_local_cover_url(None, 42) is None
    assert _normalize_local_cover_url(" ", 42) is None
    conn = _seeded_connection()
    service = FirestoreSyncService(conn=conn, client=InMemoryFirestoreClient())

    playlist_docs = [
        {
            "_doc_id": "old",
            "playlist_sync_key": "p",
            "track_title": "Song",
            "track_artist": "Artist",
            "position": 0,
            "updated_at": "1",
        },
        {
            "_doc_id": "new",
            "playlist_sync_key": "p",
            "track_title": "Song",
            "track_artist": "Artist",
            "position": 1,
            "updated_at": "2",
        },
    ]
    assert service._dedup_and_sort_playlist_tracks(playlist_docs) == [playlist_docs[1]]
    review_docs = [
        {
            "_doc_id": "active",
            "user_email": "u@example.com",
            "track_title": "Song",
            "track_artist": "Artist",
            "created_at": "now",
            "updated_at": "later",
        },
        {
            "_doc_id": "deleted",
            "user_email": "u@example.com",
            "track_title": "Song",
            "track_artist": "Artist",
            "created_at": "now",
            "is_deleted": True,
            "updated_at": "earlier",
        },
    ]
    assert service._dedup_and_sort_reviews(review_docs) == [review_docs[1]]
    interaction_docs = [
        {
            "_doc_id": "old",
            "user_email": "u@example.com",
            "track_title": "Song",
            "track_artist": "Artist",
            "updated_at": "1",
        },
        {
            "_doc_id": "new",
            "user_email": "u@example.com",
            "track_title": "Song",
            "track_artist": "Artist",
            "updated_at": "2",
        },
    ]
    assert service._dedup_and_sort_interactions(interaction_docs) == [
        interaction_docs[1]
    ]
    conn.close()


def test_full_persistent_data_sync_includes_jams_logs_access_and_settings() -> None:
    client = InMemoryFirestoreClient()
    conn_a = _seeded_connection()
    conn_b = _seeded_connection()
    try:
        user = conn_a.execute("SELECT user_id FROM users LIMIT 1").fetchone()
        track = conn_a.execute("SELECT track_id FROM tracks LIMIT 1").fetchone()
        assert user is not None
        assert track is not None
        user_id = int(user["user_id"])
        track_id = int(track["track_id"])
        now = "2026-11-25T13:00:00+00:00"

        conn_a.execute(
            "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
            ("Shared Pro", 19.5, 3),
        )
        conn_a.execute(
            """
            INSERT INTO jams (
                host_user_id, room_name, room_code, is_active, current_track_id,
                created_at, duration_minutes, max_superlikes, superlikes_used,
                skip_votes_threshold, accumulated_duration_seconds, deck_source
            ) VALUES (?, ?, ?, 1, ?, ?, 60, 10, 1, 3, 240, 'free')
            """,
            (user_id, "Shared room", "SYNC42", track_id, now),
        )
        jam_id = int(conn_a.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn_a.execute(
            "INSERT INTO jam_queue_items (jam_id, track_id, vote_points, added_at) VALUES (?, ?, ?, ?)",
            (jam_id, track_id, 7, now),
        )
        conn_a.execute(
            "INSERT INTO jam_participants (jam_id, user_id, joined_at) VALUES (?, ?, ?)",
            (jam_id, user_id, now),
        )
        conn_a.execute(
            """
            INSERT INTO jam_skip_votes (jam_id, track_id, user_id, voted_at)
            VALUES (?, ?, ?, ?)
            """,
            (jam_id, track_id, user_id, now),
        )
        conn_a.execute(
            "INSERT INTO audit_logs (event, status, created_at) VALUES (?, ?, ?)",
            ("jam.created", "success", now),
        )
        conn_a.execute(
            "INSERT INTO track_accesses (user_id, track_id, source, accessed_at) VALUES (?, ?, ?, ?)",
            (user_id, track_id, "discovery", now),
        )
        conn_a.execute(
            """
            UPDATE platform_cost_settings
            SET content_cost_per_track = 0.12, updated_at = ?
            WHERE settings_id = 1
            """,
            (now,),
        )
        conn_a.commit()

        FirestoreSyncService(conn=conn_a, client=client).sync_all()
        FirestoreSyncService(conn=conn_b, client=client).sync_all()

        assert (
            conn_b.execute(
                "SELECT monthly_price FROM plans WHERE name = 'Shared Pro'"
            ).fetchone()["monthly_price"]
            == 19.5
        )
        remote_jam = conn_b.execute(
            "SELECT jam_id FROM jams WHERE room_code = 'SYNC42'"
        ).fetchone()
        assert remote_jam is not None
        remote_jam_id = int(remote_jam["jam_id"])
        assert (
            conn_b.execute(
                "SELECT vote_points FROM jam_queue_items WHERE jam_id = ?",
                (remote_jam_id,),
            ).fetchone()["vote_points"]
            == 7
        )
        assert (
            conn_b.execute(
                "SELECT COUNT(*) FROM jam_participants WHERE jam_id = ?",
                (remote_jam_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn_b.execute(
                "SELECT COUNT(*) FROM jam_skip_votes WHERE jam_id = ?",
                (remote_jam_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn_b.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event = 'jam.created'"
            ).fetchone()[0]
            == 1
        )
        assert conn_b.execute("SELECT COUNT(*) FROM track_accesses").fetchone()[0] == 1
        assert (
            conn_b.execute(
                "SELECT content_cost_per_track FROM platform_cost_settings WHERE settings_id = 1"
            ).fetchone()[0]
            == 0.12
        )
    finally:
        conn_a.close()
        conn_b.close()


def test_bidirectional_sync_covers_user_reviews_playlists_and_interactions() -> None:
    client = InMemoryFirestoreClient()
    conn_a = _seeded_connection()
    conn_b = _seeded_connection()
    try:
        user = conn_a.execute("SELECT user_id, plan_id FROM users LIMIT 1").fetchone()
        track = conn_a.execute("SELECT track_id FROM tracks LIMIT 1").fetchone()
        assert user is not None
        assert track is not None
        user_id = int(user["user_id"])
        track_id = int(track["track_id"])
        plan_id = int(user["plan_id"])
        now = "2026-11-25T13:00:00+00:00"
        conn_a.execute(
            """
            INSERT INTO users (email, password_hash, display_name, plan_id, created_at)
            VALUES ('sync-friend@example.com', 'friend-hash', 'Sync Friend', ?, ?)
            """,
            (plan_id, now),
        )
        friend_id = int(conn_a.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn_a.execute(
            """
            INSERT INTO reviews (
                user_id, track_id, rating, text, likes_count, created_at
            ) VALUES (?, ?, 5, 'Shared review', 1, ?)
            """,
            (user_id, track_id, now),
        )
        review_id = int(conn_a.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn_a.execute(
            "INSERT INTO review_likes (review_id, user_id, created_at) VALUES (?, ?, ?)",
            (review_id, friend_id, now),
        )
        conn_a.execute(
            """
            INSERT INTO playlists (
                user_id, name, description, created_at, cover_image_url
            ) VALUES (?, 'Shared playlist', 'Sync test', ?, '/api/playlists/99/image')
            """,
            (user_id, now),
        )
        playlist_id = int(conn_a.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn_a.execute(
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, added_at)
            VALUES (?, ?, ?)
            """,
            (playlist_id, track_id, now),
        )
        conn_a.execute(
            """
            INSERT INTO playlist_images (playlist_id, content_type, image_data, updated_at)
            VALUES (?, 'image/png', ?, ?)
            """,
            (playlist_id, b"cover-bytes", now),
        )
        conn_a.execute(
            """
            INSERT INTO interactions (user_id, track_id, action, created_at, source)
            VALUES (?, ?, 'like', ?, 'discovery')
            """,
            (friend_id, track_id, now),
        )
        conn_a.commit()

        FirestoreSyncService(conn=conn_a, client=client).sync_all()
        FirestoreSyncService(conn=conn_b, client=client).sync_all()

        assert (
            conn_b.execute(
                "SELECT display_name FROM users WHERE email = 'sync-friend@example.com'"
            ).fetchone()["display_name"]
            == "Sync Friend"
        )
        assert (
            conn_b.execute(
                "SELECT text FROM reviews WHERE text = 'Shared review'"
            ).fetchone()["text"]
            == "Shared review"
        )
        assert conn_b.execute("SELECT COUNT(*) FROM review_likes").fetchone()[0] == 1
        remote_playlist = conn_b.execute(
            "SELECT playlist_id, cover_image_url FROM playlists WHERE name = 'Shared playlist'"
        ).fetchone()
        assert remote_playlist is not None
        remote_playlist_id = int(remote_playlist["playlist_id"])
        assert remote_playlist["cover_image_url"] == (
            f"/api/playlists/{remote_playlist_id}/image"
        )
        assert (
            conn_b.execute(
                "SELECT image_data FROM playlist_images WHERE playlist_id = ?",
                (remote_playlist_id,),
            ).fetchone()["image_data"]
            == b"cover-bytes"
        )
        assert (
            conn_b.execute(
                """
            SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?
            """,
                (remote_playlist_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn_b.execute(
                """
            SELECT action FROM interactions
            WHERE user_id = (SELECT user_id FROM users WHERE email = 'sync-friend@example.com')
            """
            ).fetchone()["action"]
            == "like"
        )
    finally:
        conn_a.close()
        conn_b.close()


def test_pull_applies_all_remote_persistent_collections() -> None:
    client = InMemoryFirestoreClient()
    now = "2026-11-25T13:00:00+00:00"
    track = {
        "track_spotify_id": "sync-track",
        "track_title": "Cloud Song",
        "track_artist": "Cloud Artist",
        "track_duration_seconds": 200,
        "track_genre": "Indie",
        "track_country": "US",
        "track_release_year": 2025,
        "track_cover_url": "https://example.test/cover.jpg",
        "track_preview_url": "https://example.test/preview.mp3",
        "track_explicit": False,
    }
    client.upsert_document(
        "plans",
        "plan",
        {"name": "Cloud Plan", "monthly_price": 9.5, "max_profiles": 2},
    )
    client.upsert_document(
        "users",
        "author",
        {
            "email": "cloud-author@example.com",
            "password_hash": "author-hash",
            "display_name": "Cloud Author",
            "plan_name": "Cloud Plan",
            "created_at": now,
            "updated_at": now,
        },
    )
    client.upsert_document(
        "users",
        "liker",
        {
            "email": "cloud-liker@example.com",
            "password_hash": "liker-hash",
            "display_name": "Cloud Liker",
            "created_at": now,
            "updated_at": now,
        },
    )
    client.upsert_document(
        "reviews",
        "review",
        {
            "user_email": "cloud-author@example.com",
            "author_name": "Cloud Author",
            "rating": 5,
            "text": "From cloud",
            "likes_count": 1,
            "created_at": now,
            "updated_at": now,
            **track,
        },
    )
    client.upsert_document(
        "review_likes",
        "like",
        {
            "review_user_email": "cloud-author@example.com",
            "review_created_at": now,
            "user_email": "cloud-liker@example.com",
            "created_at": now,
            "updated_at": now,
            **track,
        },
    )
    client.upsert_document(
        "playlists",
        "playlist",
        {
            "user_email": "cloud-author@example.com",
            "name": "Cloud playlist",
            "description": "Remote playlist",
            "created_at": now,
            "cover_image_url": "/api/playlists/8/image",
            "updated_at": now,
        },
    )
    client.upsert_document(
        "playlist_images",
        "image",
        {
            "user_email": "cloud-author@example.com",
            "playlist_created_at": now,
            "content_type": "image/png",
            "image_data_b64": "Y2xvdWQtaW1hZ2U=",
            "updated_at": now,
        },
    )
    client.upsert_document(
        "playlist_tracks",
        "playlist-track",
        {
            "user_email": "cloud-author@example.com",
            "playlist_created_at": now,
            "position": 0,
            "added_at": now,
            "updated_at": now,
            **track,
        },
    )
    client.upsert_document(
        "interactions",
        "interaction",
        {
            "user_email": "cloud-liker@example.com",
            "action": "like",
            "source": "discovery",
            "created_at": now,
            "updated_at": now,
            **track,
        },
    )
    client.upsert_document(
        "jams",
        "jam",
        {
            "room_code": "CLOUD42",
            "room_name": "Cloud jam",
            "host_email": "cloud-author@example.com",
            "is_active": True,
            "created_at": now,
            "current_track": track,
            "queue": [{**track, "vote_points": 2, "added_at": now}],
            "participants": [{"email": "cloud-liker@example.com", "joined_at": now}],
            "skip_votes": [
                {**track, "user_email": "cloud-liker@example.com", "voted_at": now}
            ],
            "updated_at": now,
        },
    )
    client.upsert_document(
        "audit_logs",
        "cloud-log",
        {"event": "cloud.sync", "status": "ok", "created_at": now, "updated_at": now},
    )
    client.upsert_document(
        "track_accesses",
        "cloud-access",
        {
            "user_email": "cloud-liker@example.com",
            "source": "discovery",
            "accessed_at": now,
            "updated_at": now,
            **track,
        },
    )
    client.upsert_document(
        "platform_cost_settings",
        "default",
        {
            "content_cost_per_track": 0.15,
            "infrastructure_fixed_cost": 12,
            "infrastructure_cost_per_user": 0.75,
            "updated_at": now,
        },
    )
    conn = _seeded_connection()
    try:
        service = FirestoreSyncService(conn=conn, client=client)
        assert service.pull_deltas(force=True)

        assert (
            conn.execute(
                "SELECT monthly_price FROM plans WHERE name = 'Cloud Plan'"
            ).fetchone()[0]
            == 9.5
        )
        assert (
            conn.execute(
                "SELECT display_name FROM users WHERE email = 'cloud-author@example.com'"
            ).fetchone()[0]
            == "Cloud Author"
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE text = 'From cloud'"
            ).fetchone()[0]
            == 1
        )
        assert conn.execute("SELECT COUNT(*) FROM review_likes").fetchone()[0] == 1
        playlist = conn.execute(
            "SELECT playlist_id FROM playlists WHERE name = 'Cloud playlist'"
        ).fetchone()
        assert playlist is not None
        playlist_id = int(playlist["playlist_id"])
        assert (
            conn.execute(
                "SELECT image_data FROM playlist_images WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()[0]
            == b"cloud-image"
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()[0]
            == 1
        )
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM jam_queue_items").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM jam_participants").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM jam_skip_votes").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event = 'cloud.sync'"
            ).fetchone()[0]
            == 1
        )
        assert conn.execute("SELECT COUNT(*) FROM track_accesses").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT content_cost_per_track FROM platform_cost_settings WHERE settings_id = 1"
            ).fetchone()[0]
            == 0.15
        )
    finally:
        conn.close()


def test_firestore_write_failures_are_propagated() -> None:
    class FailingFirestoreClient(InMemoryFirestoreClient):
        def upsert_document(
            self, collection: str, doc_id: str, data: dict[str, Any]
        ) -> None:
            raise ExternalServiceError(
                "Firestore unavailable", service_name="GCP_Firestore"
            )

    conn = _seeded_connection()
    try:
        service = FirestoreSyncService(conn=conn, client=FailingFirestoreClient())
        repository = SQLiteAuditLogRepository(conn, sync_service=service)

        with pytest.raises(ExternalServiceError, match="Firestore unavailable"):
            repository.log_event("test.sync", "success")
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event = 'test.sync'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_user_deletion_removes_user_from_remote_jams_and_track_accesses() -> None:
    client = InMemoryFirestoreClient()
    client.upsert_document(
        "track_accesses",
        "access-user",
        {"user_email": "user@example.com"},
    )
    client.upsert_document(
        "track_accesses",
        "access-other",
        {"user_email": "other@example.com"},
    )
    client.upsert_document(
        "jams",
        "jam-1",
        {
            "host_email": "host@example.com",
            "participants": [
                {"email": "user@example.com"},
                {"email": "other@example.com"},
            ],
            "skip_votes": [
                {"user_email": "user@example.com"},
                {"user_email": "other@example.com"},
            ],
        },
    )
    conn = _seeded_connection()
    try:
        FirestoreSyncService(conn=conn, client=client).push_user_deleted(
            "user@example.com"
        )

        assert "access-user" not in client.documents["track_accesses"]
        assert "access-other" in client.documents["track_accesses"]
        assert "jam-1" in client.documents["jams"]
        jam = client.documents["jams"]["jam-1"]
        assert jam["participants"] == [{"email": "other@example.com"}]
        assert jam["skip_votes"] == [{"user_email": "other@example.com"}]
    finally:
        conn.close()


def test_delete_preparation_and_tombstones_preserve_remote_delete_state() -> None:
    client = InMemoryFirestoreClient()
    conn = _seeded_connection()
    try:
        user = conn.execute("SELECT user_id, email FROM users LIMIT 1").fetchone()
        track = conn.execute("SELECT track_id FROM tracks LIMIT 1").fetchone()
        assert user is not None
        assert track is not None
        user_id = int(user["user_id"])
        track_id = int(track["track_id"])
        email = str(user["email"])
        created_at = "2026-11-25T13:00:00+00:00"
        conn.execute(
            "INSERT INTO reviews (user_id, track_id, rating, created_at) VALUES (?, ?, 4, ?)",
            (user_id, track_id, created_at),
        )
        review_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            "INSERT INTO review_likes (review_id, user_id, created_at) VALUES (?, ?, ?)",
            (review_id, user_id, created_at),
        )
        conn.execute(
            "INSERT INTO playlists (user_id, name, created_at) VALUES (?, 'Delete me', ?)",
            (user_id, created_at),
        )
        playlist_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            "INSERT INTO playlist_tracks (playlist_id, track_id, added_at) VALUES (?, ?, ?)",
            (playlist_id, track_id, created_at),
        )
        conn.execute(
            "INSERT INTO interactions (user_id, track_id, action, created_at) VALUES (?, ?, 'like', ?)",
            (user_id, track_id, created_at),
        )
        service = FirestoreSyncService(conn=conn, client=client)
        with transaction(conn) as cursor:
            child_docs = service.prepare_user_delete(cursor, user_id, email)

        assert {collection for collection, _doc_id in child_docs} == {
            "reviews",
            "review_likes",
            "playlists",
            "playlist_images",
            "playlist_tracks",
            "interactions",
        }
        service.push_user_deleted(email, child_docs)
        assert client.get_document("users", user_doc_id(email))["is_deleted"]
        assert (
            conn.execute(
                "SELECT is_deleted FROM _firestore_user_tombstones WHERE email = ?",
                (email.lower(),),
            ).fetchone()[0]
            == 1
        )

        service.push_playlist_deleted(email, created_at)
        playlist_key = playlist_doc_id(email, created_at)
        assert client.get_document("playlists", playlist_key)["is_deleted"]
        client.delete_document("playlists", playlist_key)
        service._push_pending_playlist_tombstones()
        assert client.get_document("playlists", playlist_key)["is_deleted"]

        service._push_pending_user_tombstones()
        assert client.get_document("users", user_doc_id(email))["is_deleted"]
    finally:
        conn.close()


def test_pull_throttling_and_failed_batch_roll_back_local_changes() -> None:
    client = InMemoryFirestoreClient()
    conn = _seeded_connection()
    try:
        service = FirestoreSyncService(
            conn=conn, client=client, min_pull_interval_seconds=60
        )
        assert service.pull_deltas()
        assert service.pull_deltas()
        client.upsert_document(
            "reviews",
            "invalid-review",
            {
                "user_email": "bad@example.com",
                "rating": ["not", "an", "integer"],
                "track_title": "Bad Song",
                "track_artist": "Bad Artist",
                "created_at": "2026-11-25T13:00:00+00:00",
                "updated_at": "2026-11-25T13:00:00+00:00",
            },
        )
        with pytest.raises(TypeError):
            service.pull_deltas(force=True)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM users WHERE email = 'bad@example.com'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM tracks WHERE title = 'Bad Song'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()
