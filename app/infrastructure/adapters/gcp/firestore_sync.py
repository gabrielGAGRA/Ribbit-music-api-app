"""Bidirectional hybrid synchronization between local SQLite and Google Cloud Firestore."""

import base64
import hashlib
import logging
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.infrastructure.repositories.connection import transaction

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Mapping, Sequence

    from app.infrastructure.adapters.gcp.firestore_client import FirestoreRestClient

logger = logging.getLogger("app.infrastructure.firestore_sync")

_MAX_IMAGE_BYTES = 700_000
_MAX_PENDING_LIKE_ATTEMPTS = 3
_SYNC_OVERLAP_SECONDS = 60
_SYNC_PLACEHOLDER_HASH = "!synced-placeholder"  # noqa: S105
_SAFE_KEY_RE = re.compile(r"[^a-zA-Z0-9_-]")
_INTERNAL_COVER_RE = re.compile(r"^/api/playlists/\d+/(image|cover)$")


def _normalize_local_cover_url(cover_url: Any, local_playlist_id: int) -> str | None:
    if cover_url is None:
        return None
    raw = str(cover_url).strip()
    if not raw:
        return None
    match = _INTERNAL_COVER_RE.match(raw)
    if match:
        return f"/api/playlists/{local_playlist_id}/{match.group(1)}"
    return raw


def _pending_like_key(doc: Mapping[str, Any]) -> str:
    raw_id = str(doc.get("_doc_id") or "").strip()
    if raw_id:
        return raw_id
    return (
        f"{_norm_email(str(doc.get('review_user_email') or ''))}"
        f"::{_norm_email(str(doc.get('user_email') or ''))}"
        f"::{str(doc.get('review_created_at') or '').strip()}"
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_iso_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso_lookback(iso_str: str, seconds: int = _SYNC_OVERLAP_SECONDS) -> str:
    try:
        parsed = datetime.fromisoformat(iso_str)
    except ValueError:
        return iso_str
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (parsed.astimezone(UTC) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _norm_email(email: str) -> str:
    return email.strip().lower()


def user_doc_id(email: str) -> str:
    """Returns a deterministic Firestore document ID for a user email."""
    return hashlib.sha256(_norm_email(email).encode("utf-8")).hexdigest()[:24]


def track_sync_key(spotify_id: str | None, title: str, artist: str) -> str:
    """Returns a cross-machine deterministic key for a track."""
    clean_sp = (spotify_id or "").strip()
    if clean_sp:
        return f"sp_{_SAFE_KEY_RE.sub('_', clean_sp)[:40]}"
    raw = f"{title.strip().lower()}::{artist.strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"ta_{digest}"


def review_doc_id(user_email: str, track_key: str, created_at: str) -> str:
    """Returns a deterministic Firestore document ID for a review."""
    raw = f"{_norm_email(user_email)}::{track_key}::{created_at.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def playlist_doc_id(user_email: str, created_at: str) -> str:
    """Returns a deterministic Firestore document ID for a playlist."""
    raw = f"{_norm_email(user_email)}::{created_at.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _track_snapshot_fields(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return {
        "track_spotify_id": row["track_spotify_id"],
        "track_title": row["track_title"],
        "track_artist": row["track_artist"],
        "track_album": row["track_album"],
        "track_duration_seconds": int(row["track_duration_seconds"] or 180),
        "track_genre": row["track_genre"] or "Pop",
        "track_country": row["track_country"],
        "track_release_year": row["track_release_year"],
        "track_cover_url": row["track_cover_url"],
        "track_preview_url": row["track_preview_url"],
        "track_explicit": bool(row["track_explicit"]),
    }


def _track_key_from_doc(doc: Mapping[str, Any]) -> str:
    return track_sync_key(
        doc.get("track_spotify_id"),
        str(doc.get("track_title") or ""),
        str(doc.get("track_artist") or ""),
    )


def _track_key_from_row(row: Mapping[str, Any] | sqlite3.Row) -> str:
    return track_sync_key(
        row["track_spotify_id"],
        str(row["track_title"] or ""),
        str(row["track_artist"] or ""),
    )


def _track_sync_keys_for_row(
    row: Mapping[str, Any] | sqlite3.Row,
) -> tuple[str, ...]:
    title = str(row["track_title"] or "")
    artist = str(row["track_artist"] or "")
    primary = track_sync_key(row["track_spotify_id"], title, artist)
    fallback = track_sync_key(None, title, artist)
    return (primary,) if primary == fallback else (primary, fallback)


class FirestoreSyncService:
    """Synchronizes 7 SQLite tables with Cloud Firestore using write-through & delta pulls."""

    COLLECTIONS = (
        "users",
        "reviews",
        "review_likes",
        "playlists",
        "playlist_images",
        "playlist_tracks",
        "interactions",
    )

    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        client: FirestoreRestClient,
        min_pull_interval_seconds: float = 2.0,
    ) -> None:
        self.conn = conn
        self.client = client
        self._min_pull_interval = min_pull_interval_seconds
        self._lock = threading.RLock()
        self._pull_lock = threading.Lock()
        self._last_pull_mono: float | None = None
        self._watermarks: dict[str, str] = {}
        self._deleted_user_emails: set[str] = set()
        self._user_deleted_at: dict[str, str] = {}
        self._pending_review_likes: dict[str, dict[str, Any]] = {}
        self._pending_like_attempts: dict[str, int] = {}
        self._exhausted_review_likes: dict[str, str] = {}
        self._deleted_playlist_keys: set[str] = set()
        self._init_sync_metadata_table()

    def _reload_tombstones_from_db(self, cursor: sqlite3.Cursor) -> None:
        rows = cursor.execute(
            "SELECT email, deleted_at, is_deleted FROM _firestore_user_tombstones"
        ).fetchall()
        pl_rows = cursor.execute(
            "SELECT pl_key FROM _firestore_playlist_tombstones"
        ).fetchall()
        with self._lock:
            self._deleted_user_emails.clear()
            self._user_deleted_at.clear()
            self._deleted_playlist_keys.clear()
            for row in rows:
                clean = _norm_email(str(row["email"]))
                if not clean:
                    continue
                if row["deleted_at"]:
                    self._record_user_deleted_at(clean, str(row["deleted_at"]))
                if row["is_deleted"]:
                    self._deleted_user_emails.add(clean)
            for pr in pl_rows:
                pl_key = str(pr["pl_key"] or "").strip()
                if pl_key:
                    self._deleted_playlist_keys.add(pl_key)

    def _init_sync_metadata_table(self) -> None:
        with self._lock, transaction(self.conn) as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS _firestore_user_tombstones (
                    email TEXT PRIMARY KEY,
                    deleted_at TEXT NOT NULL,
                    is_deleted INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS _firestore_playlist_tombstones (
                    pl_key TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    deleted_at TEXT NOT NULL
                )
                """
            )
            self._reload_tombstones_from_db(cursor)

    def _record_user_deleted_at(self, email: str, deleted_at: str) -> None:
        clean = _norm_email(email)
        if not clean or not deleted_at:
            return
        with self._lock:
            existing = self._user_deleted_at.get(clean)
            if existing is None:
                self._user_deleted_at[clean] = deleted_at
                return
            existing_dt = _parse_iso_utc(existing)
            new_dt = _parse_iso_utc(deleted_at)
            if existing_dt is None or (new_dt is not None and new_dt > existing_dt):
                self._user_deleted_at[clean] = deleted_at

    def _persist_user_tombstone_state(
        self,
        cursor: sqlite3.Cursor | None,
        email: str,
        deleted_at: str,
        *,
        is_deleted: bool,
    ) -> None:
        clean = _norm_email(email)
        if not clean:
            return
        with self._lock:
            if deleted_at:
                self._record_user_deleted_at(clean, deleted_at)
            if is_deleted:
                self._deleted_user_emails.add(clean)
            else:
                self._deleted_user_emails.discard(clean)
            effective_deleted_at = deleted_at or self._user_deleted_at.get(clean, "")
        if not effective_deleted_at:
            return
        sql = """
            INSERT INTO _firestore_user_tombstones (email, deleted_at, is_deleted)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                deleted_at = CASE
                    WHEN excluded.deleted_at > _firestore_user_tombstones.deleted_at
                    THEN excluded.deleted_at
                    ELSE _firestore_user_tombstones.deleted_at
                END,
                is_deleted = excluded.is_deleted
        """
        params = (clean, effective_deleted_at, 1 if is_deleted else 0)
        if cursor is not None:
            cursor.execute(sql, params)
            return
        with self._lock, transaction(self.conn) as tx_cursor:
            tx_cursor.execute(sql, params)

    def _persist_playlist_tombstone(
        self,
        cursor: sqlite3.Cursor | None,
        pl_key: str,
        user_email: str,
        created_at: str,
        deleted_at: str,
    ) -> None:
        clean_key = pl_key.strip()
        clean_email = _norm_email(user_email)
        clean_created = created_at.strip()
        if not clean_key or not clean_email or not clean_created:
            return
        with self._lock:
            self._deleted_playlist_keys.add(clean_key)
        sql = """
            INSERT INTO _firestore_playlist_tombstones (
                pl_key, user_email, created_at, deleted_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(pl_key) DO UPDATE SET
                deleted_at = excluded.deleted_at
        """
        params = (clean_key, clean_email, clean_created, deleted_at or _utc_now_iso())
        if cursor is not None:
            cursor.execute(sql, params)
            return
        with self._lock, transaction(self.conn) as tx_cursor:
            tx_cursor.execute(sql, params)

    def _get_remote_doc(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        get_fn = getattr(self.client, "get_document", None)
        if not callable(get_fn):
            return None
        doc = get_fn(collection, doc_id)
        return doc if isinstance(doc, dict) else None

    def _safe_run(self, action: str, fn: Callable[[], None]) -> bool:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Firestore sync skipped during %s: %s", action, exc)
            return False
        else:
            return True

    # ------------------------------------------------------------------
    # Write-through pushes (SQLite -> Firestore)
    # ------------------------------------------------------------------

    def push_user_by_id(self, user_id: int) -> None:
        """Pushes a user row to Firestore."""
        self._safe_run(f"push_user({user_id})", lambda: self._push_user(user_id))

    def prepare_user_delete(
        self, cursor: sqlite3.Cursor, user_id: int, email: str
    ) -> list[tuple[str, str]]:
        """Collects Firestore document references for a user before SQLite cascade deletion."""
        clean_email = _norm_email(email)
        if not clean_email:
            return []
        docs: list[tuple[str, str]] = []
        docs.extend(self._collect_deleted_review_docs(cursor, user_id, clean_email))
        docs.extend(self._collect_deleted_review_like_docs(cursor, user_id))
        docs.extend(self._collect_deleted_playlist_docs(cursor, user_id, clean_email))
        docs.extend(
            self._collect_deleted_interaction_docs(cursor, user_id, clean_email)
        )
        return list(dict.fromkeys(docs))

    def _collect_deleted_review_docs(
        self, cursor: sqlite3.Cursor, user_id: int, clean_email: str
    ) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        rows = cursor.execute(
            """
            SELECT
                r.created_at,
                t.spotify_id AS track_spotify_id,
                t.title AS track_title,
                t.artist AS track_artist
            FROM reviews r
            JOIN tracks t ON t.track_id = r.track_id
            WHERE r.user_id = ?
            """,
            (user_id,),
        ).fetchall()
        for row in rows:
            created_at = str(row["created_at"] or "")
            docs.extend(
                ("reviews", review_doc_id(clean_email, t_key, created_at))
                for t_key in _track_sync_keys_for_row(row)
            )
        return docs

    def _collect_deleted_review_like_docs(
        self, cursor: sqlite3.Cursor, user_id: int
    ) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        rows = cursor.execute(
            """
            SELECT
                u_liker.email AS liker_email,
                u_author.email AS rev_email,
                r.created_at AS rev_created_at,
                t.spotify_id AS track_spotify_id,
                t.title AS track_title,
                t.artist AS track_artist
            FROM review_likes rl
            JOIN users u_liker ON u_liker.user_id = rl.user_id
            JOIN reviews r ON r.review_id = rl.review_id
            JOIN users u_author ON u_author.user_id = r.user_id
            JOIN tracks t ON t.track_id = r.track_id
            WHERE rl.user_id = ? OR r.user_id = ?
            """,
            (user_id, user_id),
        ).fetchall()
        for row in rows:
            rev_email = str(row["rev_email"] or "").strip()
            liker_email = str(row["liker_email"] or "").strip()
            if not rev_email or not liker_email:
                continue
            liker_doc = user_doc_id(liker_email)
            rev_created = str(row["rev_created_at"] or "")
            docs.extend(
                (
                    "review_likes",
                    f"{review_doc_id(rev_email, t_key, rev_created)}__{liker_doc}",
                )
                for t_key in _track_sync_keys_for_row(row)
            )
        return docs

    def _collect_deleted_playlist_docs(
        self, cursor: sqlite3.Cursor, user_id: int, clean_email: str
    ) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        pl_rows = cursor.execute(
            "SELECT playlist_id, created_at FROM playlists WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        for pl_row in pl_rows:
            pl_key = playlist_doc_id(clean_email, str(pl_row["created_at"] or ""))
            docs.append(("playlists", pl_key))
            docs.append(("playlist_images", pl_key))
            tr_rows = cursor.execute(
                """
                SELECT
                    t.spotify_id AS track_spotify_id,
                    t.title AS track_title,
                    t.artist AS track_artist
                FROM playlist_tracks pt
                JOIN tracks t ON t.track_id = pt.track_id
                WHERE pt.playlist_id = ?
                """,
                (int(pl_row["playlist_id"]),),
            ).fetchall()
            docs.extend(
                ("playlist_tracks", f"{pl_key}__{t_key}")
                for tr in tr_rows
                for t_key in _track_sync_keys_for_row(tr)
            )
        return docs

    def _collect_deleted_interaction_docs(
        self, cursor: sqlite3.Cursor, user_id: int, clean_email: str
    ) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        u_doc = user_doc_id(clean_email)
        rows = cursor.execute(
            """
            SELECT
                t.spotify_id AS track_spotify_id,
                t.title AS track_title,
                t.artist AS track_artist
            FROM interactions i
            JOIN tracks t ON t.track_id = i.track_id
            WHERE i.user_id = ?
            """,
            (user_id,),
        ).fetchall()
        docs.extend(
            ("interactions", f"{u_doc}__{t_key}")
            for row in rows
            for t_key in _track_sync_keys_for_row(row)
        )
        return docs

    def _delete_user_cloud_docs(
        self,
        clean_email: str,
        now_iso: str,
        child_docs: Sequence[tuple[str, str]],
    ) -> None:
        self.client.upsert_document(
            "users",
            user_doc_id(clean_email),
            {
                "email": clean_email,
                "is_deleted": True,
                "deleted_at": now_iso,
                "updated_at": now_iso,
            },
        )
        for col, doc_id in dict.fromkeys(child_docs):
            try:
                self.client.delete_document(col, doc_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Firestore child delete skipped during user purge (%s/%s): %s",
                    col,
                    doc_id,
                    exc,
                )

    def push_user_deleted(
        self, email: str, child_docs: Sequence[tuple[str, str]] = ()
    ) -> None:
        """Marks a user deleted in Firestore and deletes their child documents."""
        clean_email = _norm_email(email)
        if not clean_email:
            return
        now_iso = _utc_now_iso()
        with self._lock:
            self._persist_user_tombstone_state(
                None, clean_email, now_iso, is_deleted=True
            )
            stale_like_keys = [
                key
                for key, doc in self._pending_review_likes.items()
                if _norm_email(str(doc.get("user_email") or "")) == clean_email
                or _norm_email(str(doc.get("review_user_email") or "")) == clean_email
            ]
            for key in stale_like_keys:
                self._clear_pending_like(key)
        self._safe_run(
            f"push_user_deleted({clean_email})",
            lambda: self._delete_user_cloud_docs(clean_email, now_iso, child_docs),
        )

    def push_review_by_id(self, review_id: int) -> None:
        """Pushes a review row (with track metadata snapshot) to Firestore."""
        self._safe_run(
            f"push_review({review_id})", lambda: self._push_review(review_id)
        )

    def push_review_like(self, review_id: int, user_id: int) -> None:
        """Pushes a review_likes entry and updates the parent review likes_count."""
        self._safe_run(
            f"push_review_like({review_id}, {user_id})",
            lambda: self._push_review_like(review_id, user_id),
        )

    def push_playlist_by_id(self, playlist_id: int) -> None:
        """Pushes a playlist and its playlist_tracks rows to Firestore."""
        self._safe_run(
            f"push_playlist({playlist_id})", lambda: self._push_playlist(playlist_id)
        )

    def push_playlist_deleted(self, user_email: str, created_at: str) -> None:
        """Marks a playlist deleted in Firestore."""
        clean_email = _norm_email(user_email)
        clean_created = created_at.strip()
        if not clean_email or not clean_created:
            return
        doc_id = playlist_doc_id(clean_email, clean_created)
        now_iso = _utc_now_iso()
        self._persist_playlist_tombstone(
            None, doc_id, clean_email, clean_created, now_iso
        )
        self._safe_run(
            f"push_playlist_deleted({doc_id})",
            lambda: self.client.upsert_document(
                "playlists",
                doc_id,
                {
                    "sync_key": doc_id,
                    "user_email": clean_email,
                    "created_at": clean_created,
                    "is_deleted": True,
                    "updated_at": now_iso,
                },
            ),
        )

    def push_playlist_track_removed(self, playlist_id: int, track_id: int) -> None:
        """Marks a playlist_tracks entry removed in Firestore."""
        self._safe_run(
            f"push_playlist_track_removed({playlist_id}, {track_id})",
            lambda: self._push_playlist_track_removed(playlist_id, track_id),
        )

    def push_playlist_image(self, playlist_id: int) -> None:
        """Pushes a playlist cover image blob to Firestore playlist_images."""
        self._safe_run(
            f"push_playlist_image({playlist_id})",
            lambda: self._push_playlist_image(playlist_id),
        )

    def push_interaction(
        self,
        user_id: int,
        track_id: int,
        *,
        is_deleted: bool = False,
    ) -> None:
        """Pushes an interaction row (or deletion tombstone) to Firestore."""
        self._safe_run(
            f"push_interaction({user_id}, {track_id})",
            lambda: self._push_interaction(user_id, track_id, is_deleted=is_deleted),
        )

    # ------------------------------------------------------------------
    # Internal push implementations (read SQLite fast, then do HTTP)
    # ------------------------------------------------------------------

    @staticmethod
    def _remote_deleted_at(remote_user: Mapping[str, Any] | None) -> str:
        if remote_user is None:
            return ""
        remote_del = str(remote_user.get("deleted_at") or "").strip()
        if not remote_del and remote_user.get("is_deleted"):
            return str(remote_user.get("updated_at") or "").strip()
        return remote_del

    def _extract_effective_deleted_at(
        self, email: str, remote_user: Mapping[str, Any] | None
    ) -> str | None:
        with self._lock:
            local_del = self._user_deleted_at.get(email)
        remote_del = self._remote_deleted_at(remote_user)
        if not local_del:
            return remote_del or None
        if not remote_del:
            return local_del
        local_dt = _parse_iso_utc(local_del)
        remote_dt = _parse_iso_utc(remote_del)
        if local_dt is not None and remote_dt is not None:
            return remote_del if remote_dt > local_dt else local_del
        return max(local_del, remote_del)

    @staticmethod
    def _is_local_user_stale_for_push(
        row: sqlite3.Row,
        remote_user: Mapping[str, Any] | None,
        deleted_at: str | None,
    ) -> bool:
        local_created_dt = _parse_iso_utc(row["created_at"])
        cutoff_dt = _parse_iso_utc(deleted_at)
        if (
            cutoff_dt is not None
            and local_created_dt is not None
            and local_created_dt <= cutoff_dt
        ):
            return True
        if remote_user and not remote_user.get("is_deleted"):
            remote_created_dt = _parse_iso_utc(remote_user.get("created_at"))
            if (
                remote_created_dt is not None
                and local_created_dt is not None
                and local_created_dt < remote_created_dt
            ):
                return True
        return False

    def _is_pushed_primary_stale(self, pri_email: str, row: sqlite3.Row) -> bool:
        with self._lock:
            is_local_del = pri_email in self._deleted_user_emails
        if is_local_del:
            return True
        remote_pri = self._get_remote_doc("users", user_doc_id(pri_email))
        if remote_pri is not None and bool(remote_pri.get("is_deleted")):
            return True
        local_pri_dt = (
            _parse_iso_utc(row["primary_user_created_at"])
            if row["primary_user_password_hash"] != _SYNC_PLACEHOLDER_HASH
            else None
        )
        if local_pri_dt is None:
            return False
        pri_del_dt = _parse_iso_utc(
            self._extract_effective_deleted_at(pri_email, remote_pri)
        )
        if pri_del_dt is not None and local_pri_dt <= pri_del_dt:
            return True
        if remote_pri is not None and not remote_pri.get("is_deleted"):
            remote_pri_dt = _parse_iso_utc(remote_pri.get("created_at"))
            if remote_pri_dt is not None and local_pri_dt < remote_pri_dt:
                return True
        return False

    def _sanitize_pushed_primary_ref(
        self, row: sqlite3.Row, user_id: int
    ) -> tuple[str | None, int, Any]:
        raw_pri = row["primary_user_email"]
        plan_id = int(row["plan_id"])
        plan_name = row["plan_name"]
        if not raw_pri:
            return None, plan_id, plan_name
        pri_email = _norm_email(str(raw_pri))
        if not pri_email:
            return None, plan_id, plan_name
        if self._is_pushed_primary_stale(pri_email, row):
            with self._lock, transaction(self.conn) as cursor:
                free_plan_id = self._resolve_free_plan_id(cursor)
                cursor.execute(
                    "UPDATE users SET primary_account_id = NULL, plan_id = ? WHERE user_id = ?",
                    (free_plan_id, user_id),
                )
            return None, free_plan_id, "Free"
        return pri_email, plan_id, plan_name

    def _push_user_payload(
        self,
        row: sqlite3.Row,
        email: str,
        deleted_at: str | None,
        primary_user_email: str | None,
        plan_id: int,
        plan_name: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "email": email,
            "password_hash": row["password_hash"],
            "spotify_id": row["spotify_id"],
            "spotify_premium": bool(row["spotify_premium"]),
            "display_name": row["display_name"],
            "age": row["age"],
            "birth_date": row["birth_date"],
            "plan_id": plan_id,
            "plan_name": plan_name,
            "primary_user_email": primary_user_email,
            "primary_user_created_at": (
                row["primary_user_created_at"]
                if primary_user_email
                and row["primary_user_password_hash"] != _SYNC_PLACEHOLDER_HASH
                else None
            ),
            "blocked_genres": row["blocked_genres"],
            "favorite_genres": row["favorite_genres"],
            "preferred_theme": row["preferred_theme"] or "dark",
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"] or _utc_now_iso(),
            "is_deleted": False,
            "updated_at": _utc_now_iso(),
        }
        if deleted_at:
            payload["deleted_at"] = deleted_at
        return payload

    def _push_user(self, user_id: int) -> None:
        row = self.conn.execute(
            """
            SELECT
                u.*,
                pl.name AS plan_name,
                pu.email AS primary_user_email,
                pu.created_at AS primary_user_created_at,
                pu.password_hash AS primary_user_password_hash
            FROM users u
            LEFT JOIN plans pl ON pl.plan_id = u.plan_id
            LEFT JOIN users pu ON pu.user_id = u.primary_account_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None or not row["email"]:
            return
        email = _norm_email(str(row["email"]))
        doc_id = user_doc_id(email)
        remote_user = self._get_remote_doc("users", doc_id)
        deleted_at = self._extract_effective_deleted_at(email, remote_user)
        if self._is_local_user_stale_for_push(row, remote_user, deleted_at):
            if deleted_at:
                is_del = (
                    bool(remote_user.get("is_deleted"))
                    if remote_user is not None
                    else email in self._deleted_user_emails
                )
                self._persist_user_tombstone_state(
                    None, email, deleted_at, is_deleted=is_del
                )
            return
        primary_user_email, plan_id, plan_name = self._sanitize_pushed_primary_ref(
            row, user_id
        )
        if deleted_at or email in self._deleted_user_emails:
            self._persist_user_tombstone_state(
                None, email, deleted_at or "", is_deleted=False
            )
        payload = self._push_user_payload(
            row, email, deleted_at, primary_user_email, plan_id, plan_name
        )
        self.client.upsert_document("users", doc_id, payload)

    def _fetch_review_row(self, review_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT
                r.*,
                u.email AS user_email,
                u.display_name AS author_name,
                t.spotify_id AS track_spotify_id,
                t.title AS track_title,
                t.artist AS track_artist,
                t.album AS track_album,
                t.duration_seconds AS track_duration_seconds,
                t.genre AS track_genre,
                t.country AS track_country,
                t.release_year AS track_release_year,
                t.cover_url AS track_cover_url,
                t.itunes_preview_url AS track_preview_url,
                t.explicit AS track_explicit
            FROM reviews r
            JOIN users u ON u.user_id = r.user_id
            JOIN tracks t ON t.track_id = r.track_id
            WHERE r.review_id = ?
            """,
            (review_id,),
        ).fetchone()

    def _backfill_track_spotify_id(
        self, track_id: int, raw_spotify_id: Any
    ) -> str | None:
        clean_sp = str(raw_spotify_id).strip() if raw_spotify_id else None
        if not clean_sp:
            return None
        with self._lock, transaction(self.conn) as cursor:
            cursor.execute(
                """
                UPDATE tracks
                SET spotify_id = COALESCE(spotify_id, ?)
                WHERE track_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM tracks WHERE spotify_id = ? AND track_id != ?
                  )
                """,
                (clean_sp, track_id, clean_sp, track_id),
            )
        return clean_sp

    def _find_matching_remote_review(self, row: sqlite3.Row) -> dict[str, Any] | None:
        target_key = "::".join(
            [
                _norm_email(str(row["user_email"])),
                str(row["track_title"] or "").strip().lower(),
                str(row["track_artist"] or "").strip().lower(),
                str(row["created_at"] or "").strip(),
            ]
        )
        matches = [
            d
            for d in self.client.list_documents("reviews")
            if isinstance(d, dict) and self._review_dedup_key(d) == target_key
        ]
        if not matches:
            return None
        return max(
            matches,
            key=lambda d: (
                1 if d.get("is_deleted") else 0,
                str(d.get("updated_at") or ""),
            ),
        )

    def _recompute_review_doc_id(self, row: sqlite3.Row, spotify_id: str) -> str:
        email = _norm_email(str(row["user_email"]))
        new_t_key = track_sync_key(
            spotify_id,
            str(row["track_title"] or ""),
            str(row["track_artist"] or ""),
        )
        return review_doc_id(email, new_t_key, str(row["created_at"] or _utc_now_iso()))

    def _resolve_counterpart_remote_review(
        self, row: sqlite3.Row, doc_id: str, t_key: str
    ) -> tuple[dict[str, Any] | None, str]:
        effective_doc_id = doc_id
        remote_rev = self._get_remote_doc("reviews", doc_id)
        if remote_rev is not None and remote_rev.get("is_deleted"):
            return remote_rev, effective_doc_id
        if t_key.startswith("ta_"):
            matched = self._find_matching_remote_review(row)
            if matched is not None:
                remote_rev = matched
                clean_sp = self._backfill_track_spotify_id(
                    int(row["track_id"]), matched.get("track_spotify_id")
                )
                if clean_sp:
                    effective_doc_id = self._recompute_review_doc_id(row, clean_sp)
            return remote_rev, effective_doc_id
        ta_key = track_sync_key(
            None,
            str(row["track_title"] or ""),
            str(row["track_artist"] or ""),
        )
        ta_doc_id = review_doc_id(
            _norm_email(str(row["user_email"])),
            ta_key,
            str(row["created_at"] or _utc_now_iso()),
        )
        ta_rev = self._get_remote_doc("reviews", ta_doc_id)
        if ta_rev is not None and ta_rev.get("is_deleted"):
            return ta_rev, effective_doc_id
        return remote_rev, effective_doc_id

    def _sync_remote_review_deleted(
        self,
        review_id: int,
        row: sqlite3.Row,
        doc_id: str,
        t_key: str,
        is_deleted: bool,
    ) -> tuple[bool, str]:
        remote_rev, effective_doc_id = self._resolve_counterpart_remote_review(
            row, doc_id, t_key
        )
        if is_deleted:
            return True, effective_doc_id
        if remote_rev is not None and remote_rev.get("is_deleted"):
            with self._lock, transaction(self.conn) as cursor:
                cursor.execute(
                    "UPDATE reviews SET is_deleted = 1 WHERE review_id = ?",
                    (review_id,),
                )
            return True, effective_doc_id
        return False, effective_doc_id

    def _push_review(self, review_id: int) -> None:
        row = self._fetch_review_row(review_id)
        if row is None or not row["user_email"]:
            return
        actual_row = self.conn.execute(
            "SELECT COUNT(*) FROM review_likes WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        actual_likes = int(actual_row[0]) if actual_row is not None else 0
        likes_count = max(int(row["likes_count"]), actual_likes)
        if likes_count != int(row["likes_count"]):
            with self._lock, transaction(self.conn) as cursor:
                cursor.execute(
                    "UPDATE reviews SET likes_count = ? WHERE review_id = ?",
                    (likes_count, review_id),
                )
        email = _norm_email(str(row["user_email"]))
        t_key = _track_key_from_row(row)
        created_at = str(row["created_at"] or _utc_now_iso())
        doc_id = review_doc_id(email, t_key, created_at)
        is_deleted, effective_doc_id = self._sync_remote_review_deleted(
            review_id, row, doc_id, t_key, bool(row["is_deleted"])
        )
        if effective_doc_id != doc_id:
            row = self._fetch_review_row(review_id) or row
        payload = {
            "sync_key": effective_doc_id,
            "user_email": email,
            "author_name": row["author_name"],
            "rating": int(row["rating"]),
            "text": row["text"],
            "likes_count": likes_count,
            "is_deleted": is_deleted,
            "created_at": created_at,
            "updated_at": _utc_now_iso(),
            **_track_snapshot_fields(row),
        }
        self.client.upsert_document("reviews", effective_doc_id, payload)
        ta_key = track_sync_key(
            None,
            str(row["track_title"] or ""),
            str(row["track_artist"] or ""),
        )
        stale_ta_id = review_doc_id(email, ta_key, created_at)
        if stale_ta_id != effective_doc_id:
            self.client.delete_document("reviews", stale_ta_id)

    def _push_review_like(self, review_id: int, user_id: int) -> None:
        self._push_review(review_id)
        rev_row = self._fetch_review_row(review_id)
        like_row = self.conn.execute(
            """
            SELECT rl.created_at, u.email AS liker_email
            FROM review_likes rl
            JOIN users u ON u.user_id = rl.user_id
            WHERE rl.review_id = ? AND rl.user_id = ?
            """,
            (review_id, user_id),
        ).fetchone()
        if rev_row is None or like_row is None:
            return
        if rev_row["is_deleted"]:
            with self._lock, transaction(self.conn) as cursor:
                cursor.execute(
                    "DELETE FROM review_likes WHERE review_id = ? AND user_id = ?",
                    (review_id, user_id),
                )
            return
        rev_email = _norm_email(str(rev_row["user_email"]))
        liker_email = _norm_email(str(like_row["liker_email"]))
        t_key = _track_key_from_row(rev_row)
        rev_created_at = str(rev_row["created_at"] or _utc_now_iso())
        rev_key = review_doc_id(rev_email, t_key, rev_created_at)
        like_doc_id = f"{rev_key}__{user_doc_id(liker_email)}"
        payload = {
            "review_sync_key": rev_key,
            "review_user_email": rev_email,
            "review_created_at": rev_created_at,
            "user_email": liker_email,
            "created_at": str(like_row["created_at"] or _utc_now_iso()),
            "updated_at": _utc_now_iso(),
            **_track_snapshot_fields(rev_row),
        }
        self.client.upsert_document("review_likes", like_doc_id, payload)
        ta_key = track_sync_key(
            None,
            str(rev_row["track_title"] or ""),
            str(rev_row["track_artist"] or ""),
        )
        if ta_key != t_key:
            stale_rev_key = review_doc_id(rev_email, ta_key, rev_created_at)
            self.client.delete_document(
                "review_likes", f"{stale_rev_key}__{user_doc_id(liker_email)}"
            )

    def _delete_stale_ta_track_doc(
        self, pl_key: str, t_key: str, title: str, artist: str
    ) -> None:
        ta_key = track_sync_key(None, title, artist)
        if ta_key != t_key:
            self.client.delete_document("playlist_tracks", f"{pl_key}__{ta_key}")

    def _sync_playlist_track_doc(
        self,
        pl_key: str,
        email: str,
        created_at: str,
        position: int,
        t_row: sqlite3.Row,
        now_iso: str,
    ) -> None:
        t_key = _track_key_from_row(t_row)
        pt_doc_id = f"{pl_key}__{t_key}"
        self.client.upsert_document(
            "playlist_tracks",
            pt_doc_id,
            {
                "playlist_sync_key": pl_key,
                "user_email": email,
                "playlist_created_at": created_at,
                "position": position,
                "added_at": str(t_row["added_at"] or now_iso),
                "is_removed": False,
                "updated_at": now_iso,
                **_track_snapshot_fields(t_row),
            },
        )
        self._delete_stale_ta_track_doc(
            pl_key,
            t_key,
            str(t_row["track_title"] or ""),
            str(t_row["track_artist"] or ""),
        )

    def _sync_remote_playlist_deleted(
        self, playlist_id: int, pl_key: str, user_email: str, created_at: str
    ) -> bool:
        with self._lock:
            is_del = pl_key in self._deleted_playlist_keys
        if not is_del:
            remote_pl = self._get_remote_doc("playlists", pl_key)
            if remote_pl is not None and remote_pl.get("is_deleted"):
                self._persist_playlist_tombstone(
                    None,
                    pl_key,
                    user_email,
                    created_at,
                    str(remote_pl.get("updated_at") or _utc_now_iso()),
                )
                is_del = True
        if is_del:
            with self._lock, transaction(self.conn) as cursor:
                cursor.execute(
                    "DELETE FROM playlists WHERE playlist_id = ?",
                    (playlist_id,),
                )
            return True
        return False

    def _push_playlist(self, playlist_id: int) -> None:
        pl_row = self.conn.execute(
            """
            SELECT p.*, u.email AS user_email
            FROM playlists p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()
        if pl_row is None or not pl_row["user_email"]:
            return
        email = _norm_email(str(pl_row["user_email"]))
        created_at = str(pl_row["created_at"] or _utc_now_iso())
        pl_key = playlist_doc_id(email, created_at)
        if self._sync_remote_playlist_deleted(playlist_id, pl_key, email, created_at):
            return
        now_iso = _utc_now_iso()
        cover_url = self._outbound_cover_url(playlist_id, pl_row["cover_image_url"])
        src_email, src_created = self._outbound_source_playlist_ref(
            pl_row["source_playlist_id"]
        )
        pl_payload = {
            "sync_key": pl_key,
            "user_email": email,
            "name": pl_row["name"],
            "description": pl_row["description"],
            "spotify_playlist_id": pl_row["spotify_playlist_id"],
            "is_exported": bool(pl_row["is_exported"]),
            "created_at": created_at,
            "max_duration_seconds": pl_row["max_duration_seconds"],
            "deck_filters": pl_row["deck_filters"],
            "cover_image_url": cover_url,
            "source_playlist_user_email": src_email,
            "source_playlist_created_at": src_created,
            "is_deleted": False,
            "updated_at": now_iso,
        }
        self.client.upsert_document("playlists", pl_key, pl_payload)

        track_rows = self.conn.execute(
            """
            SELECT
                pt.playlist_track_id,
                pt.added_at,
                t.spotify_id AS track_spotify_id,
                t.title AS track_title,
                t.artist AS track_artist,
                t.album AS track_album,
                t.duration_seconds AS track_duration_seconds,
                t.genre AS track_genre,
                t.country AS track_country,
                t.release_year AS track_release_year,
                t.cover_url AS track_cover_url,
                t.itunes_preview_url AS track_preview_url,
                t.explicit AS track_explicit
            FROM playlist_tracks pt
            JOIN tracks t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.playlist_track_id ASC
            """,
            (playlist_id,),
        ).fetchall()
        for position, t_row in enumerate(track_rows):
            self._sync_playlist_track_doc(
                pl_key, email, created_at, position, t_row, now_iso
            )

    def _outbound_cover_url(self, playlist_id: int, cover_url: Any) -> str | None:
        if isinstance(cover_url, str) and _INTERNAL_COVER_RE.match(cover_url.strip()):
            img_meta = self.conn.execute(
                "SELECT length(image_data) AS sz FROM playlist_images WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            if img_meta is None or int(img_meta["sz"] or 0) > _MAX_IMAGE_BYTES:
                return None
        return str(cover_url) if cover_url is not None else None

    def _outbound_source_playlist_ref(
        self, source_playlist_id: Any
    ) -> tuple[str | None, str | None]:
        if source_playlist_id is None:
            return None, None
        src_row = self.conn.execute(
            """
            SELECT p.created_at, u.email AS user_email
            FROM playlists p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.playlist_id = ?
            """,
            (int(source_playlist_id),),
        ).fetchone()
        if src_row is None or not src_row["user_email"] or not src_row["created_at"]:
            return None, None
        return _norm_email(str(src_row["user_email"])), str(src_row["created_at"])

    def _push_playlist_track_removed(self, playlist_id: int, track_id: int) -> None:
        pl_row = self.conn.execute(
            """
            SELECT p.created_at, u.email AS user_email
            FROM playlists p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()
        t_row = self.conn.execute(
            "SELECT spotify_id, title, artist FROM tracks WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        if pl_row is None or t_row is None or not pl_row["user_email"]:
            return
        email = _norm_email(str(pl_row["user_email"]))
        pl_created = str(pl_row["created_at"] or "")
        pl_key = playlist_doc_id(email, pl_created)
        if pl_created and self._sync_remote_playlist_deleted(
            playlist_id, pl_key, email, pl_created
        ):
            return
        t_key = track_sync_key(
            t_row["spotify_id"], str(t_row["title"]), str(t_row["artist"])
        )
        pt_doc_id = f"{pl_key}__{t_key}"
        self.client.upsert_document(
            "playlist_tracks",
            pt_doc_id,
            {
                "playlist_sync_key": pl_key,
                "user_email": email,
                "playlist_created_at": pl_created,
                "track_spotify_id": t_row["spotify_id"],
                "track_title": t_row["title"],
                "track_artist": t_row["artist"],
                "is_removed": True,
                "updated_at": _utc_now_iso(),
            },
        )
        self._delete_stale_ta_track_doc(
            pl_key, t_key, str(t_row["title"]), str(t_row["artist"])
        )

    def _push_playlist_image(self, playlist_id: int) -> None:
        row = self.conn.execute(
            """
            SELECT
                pi.content_type,
                pi.image_data,
                pi.updated_at,
                p.created_at AS playlist_created_at,
                u.email AS user_email
            FROM playlist_images pi
            JOIN playlists p ON p.playlist_id = pi.playlist_id
            JOIN users u ON u.user_id = p.user_id
            WHERE pi.playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()
        if row is None or not row["user_email"]:
            return
        email = _norm_email(str(row["user_email"]))
        pl_created = str(row["playlist_created_at"] or "")
        pl_key = playlist_doc_id(email, pl_created)
        if pl_created and self._sync_remote_playlist_deleted(
            playlist_id, pl_key, email, pl_created
        ):
            return
        raw_bytes = bytes(row["image_data"])
        if len(raw_bytes) > _MAX_IMAGE_BYTES:
            logger.warning(
                "Skipping Firestore image sync for playlist %s: size %d exceeds %d bytes",
                playlist_id,
                len(raw_bytes),
                _MAX_IMAGE_BYTES,
            )
            self.client.delete_document("playlist_images", pl_key)
            return
        self.client.upsert_document(
            "playlist_images",
            pl_key,
            {
                "playlist_sync_key": pl_key,
                "user_email": email,
                "playlist_created_at": pl_created,
                "content_type": row["content_type"],
                "image_data_b64": base64.b64encode(raw_bytes).decode("ascii"),
                "updated_at": _utc_now_iso(),
            },
        )

    def _push_interaction(
        self,
        user_id: int,
        track_id: int,
        *,
        is_deleted: bool,
    ) -> None:
        user_row = self.conn.execute(
            "SELECT email FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        t_row = self.conn.execute(
            """
            SELECT
                spotify_id AS track_spotify_id,
                title AS track_title,
                artist AS track_artist,
                album AS track_album,
                duration_seconds AS track_duration_seconds,
                genre AS track_genre,
                country AS track_country,
                release_year AS track_release_year,
                cover_url AS track_cover_url,
                itunes_preview_url AS track_preview_url,
                explicit AS track_explicit
            FROM tracks
            WHERE track_id = ?
            """,
            (track_id,),
        ).fetchone()
        if user_row is None or t_row is None or not user_row["email"]:
            return
        email = _norm_email(str(user_row["email"]))
        t_key = _track_key_from_row(t_row)
        doc_id = f"{user_doc_id(email)}__{t_key}"
        now_iso = _utc_now_iso()

        if is_deleted:
            payload: dict[str, Any] = {
                "user_email": email,
                "is_deleted": True,
                "updated_at": now_iso,
                **_track_snapshot_fields(t_row),
            }
        else:
            int_row = self.conn.execute(
                """
                SELECT action, created_at, source
                FROM interactions
                WHERE user_id = ? AND track_id = ?
                """,
                (user_id, track_id),
            ).fetchone()
            if int_row is None:
                return
            payload = {
                "user_email": email,
                "action": int_row["action"],
                "source": int_row["source"],
                "created_at": str(int_row["created_at"] or now_iso),
                "is_deleted": False,
                "updated_at": now_iso,
                **_track_snapshot_fields(t_row),
            }
        self.client.upsert_document("interactions", doc_id, payload)
        ta_key = track_sync_key(
            None,
            str(t_row["track_title"] or ""),
            str(t_row["track_artist"] or ""),
        )
        if ta_key != t_key:
            self.client.delete_document(
                "interactions", f"{user_doc_id(email)}__{ta_key}"
            )

    # ------------------------------------------------------------------
    # Delta pulls & startup bidirectional sync (Firestore -> SQLite)
    # ------------------------------------------------------------------

    def pull_deltas(self, *, force: bool = False) -> bool:
        """Pulls recently updated documents across all 7 Firestore collections into SQLite."""
        with self._pull_lock:
            now_mono = time.monotonic()
            if (
                not force
                and self._last_pull_mono is not None
                and (now_mono - self._last_pull_mono) < self._min_pull_interval
            ):
                return True
            ok = self._safe_run("pull_deltas", self._execute_pull)
            if ok:
                self._last_pull_mono = time.monotonic()
            return ok

    @staticmethod
    def _playlist_track_dedup_key(doc: Mapping[str, Any]) -> str:
        pl_key = str(doc.get("playlist_sync_key") or "").strip()
        title = str(doc.get("track_title") or "").strip().lower()
        artist = str(doc.get("track_artist") or "").strip().lower()
        if pl_key and title and artist:
            return f"{pl_key}::{title}::{artist}"
        return str(doc.get("_doc_id") or id(doc))

    @staticmethod
    def _review_dedup_key(doc: Mapping[str, Any]) -> str:
        email = _norm_email(str(doc.get("user_email") or ""))
        title = str(doc.get("track_title") or "").strip().lower()
        artist = str(doc.get("track_artist") or "").strip().lower()
        created_at = str(doc.get("created_at") or "").strip()
        if email and title and artist and created_at:
            return f"{email}::{title}::{artist}::{created_at}"
        return str(doc.get("_doc_id") or id(doc))

    @staticmethod
    def _interaction_dedup_key(doc: Mapping[str, Any]) -> str:
        email = _norm_email(str(doc.get("user_email") or ""))
        title = str(doc.get("track_title") or "").strip().lower()
        artist = str(doc.get("track_artist") or "").strip().lower()
        if email and title and artist:
            return f"{email}::{title}::{artist}"
        return str(doc.get("_doc_id") or id(doc))

    @staticmethod
    def _doc_rank(
        doc: Mapping[str, Any], deleted_field: str, *, deleted_first: bool
    ) -> tuple[Any, ...]:
        del_flag = 1 if doc.get(deleted_field) else 0
        ts = str(doc.get("updated_at") or "")
        return (del_flag, ts) if deleted_first else (ts, del_flag)

    @classmethod
    def _dedup_latest_docs(
        cls,
        docs: list[dict[str, Any]],
        *,
        key_fn: Callable[[Mapping[str, Any]], str],
        deleted_field: str,
        deleted_first: bool = False,
    ) -> list[dict[str, Any]]:
        winners: dict[str, dict[str, Any]] = {}
        for doc in docs:
            key = key_fn(doc)
            prev = winners.get(key)
            if prev is None:
                winners[key] = doc
                continue
            prev_rank = cls._doc_rank(prev, deleted_field, deleted_first=deleted_first)
            cur_rank = cls._doc_rank(doc, deleted_field, deleted_first=deleted_first)
            if cur_rank >= prev_rank:
                winners[key] = doc
        return list(winners.values())

    @classmethod
    def _dedup_and_sort_playlist_tracks(
        cls, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        winners = cls._dedup_latest_docs(
            docs,
            key_fn=cls._playlist_track_dedup_key,
            deleted_field="is_removed",
        )
        return sorted(
            winners,
            key=lambda d: (
                str(d.get("playlist_sync_key") or ""),
                int(d.get("position") or 0),
                str(d.get("added_at") or ""),
            ),
        )

    @classmethod
    def _dedup_and_sort_reviews(
        cls, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        winners = cls._dedup_latest_docs(
            docs,
            key_fn=cls._review_dedup_key,
            deleted_field="is_deleted",
            deleted_first=True,
        )
        return sorted(
            winners,
            key=lambda d: (
                0 if d.get("is_deleted") else 1,
                str(d.get("created_at") or ""),
            ),
        )

    @classmethod
    def _dedup_and_sort_interactions(
        cls, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        winners = cls._dedup_latest_docs(
            docs,
            key_fn=cls._interaction_dedup_key,
            deleted_field="is_deleted",
        )
        return sorted(
            winners,
            key=lambda d: (
                str(d.get("updated_at") or ""),
                0 if d.get("is_deleted") else 1,
            ),
        )

    def _advance_watermarks(self, batches: Mapping[str, list[dict[str, Any]]]) -> None:
        now_iso = _utc_now_iso()
        for col, docs in batches.items():
            if col == "review_likes" and self._pending_review_likes:
                continue
            max_ts = max(
                (str(d["updated_at"]) for d in docs if d.get("updated_at")),
                default="",
            )
            if max_ts:
                capped_ts = min(max_ts, now_iso)
                if capped_ts > self._watermarks.get(col, ""):
                    self._watermarks[col] = capped_ts

    def _execute_pull(self) -> None:
        with self._lock:
            since_map = dict(self._watermarks)
        batches: dict[str, list[dict[str, Any]]] = {}
        for col in self.COLLECTIONS:
            since = since_map.get(col)
            query_since = _iso_lookback(since) if since else None
            batches[col] = self.client.query_updated_since(col, query_since)

        users_batch = sorted(
            batches["users"],
            key=lambda d: (
                0 if d.get("is_deleted") else (2 if d.get("primary_user_email") else 1),
                str(d.get("created_at") or ""),
            ),
        )
        reviews_batch = self._dedup_and_sort_reviews(batches["reviews"])
        playlists_batch = sorted(
            batches["playlists"],
            key=lambda d: (
                1 if d.get("source_playlist_created_at") else 0,
                str(d.get("created_at") or ""),
            ),
        )
        playlist_tracks_batch = self._dedup_and_sort_playlist_tracks(
            batches["playlist_tracks"]
        )
        interactions_batch = self._dedup_and_sort_interactions(batches["interactions"])

        with self._lock, transaction(self.conn) as cursor:
            merged_likes = list(
                {
                    _pending_like_key(d): d
                    for d in list(self._pending_review_likes.values())
                    + batches["review_likes"]
                }.values()
            )
            cursor.execute("SAVEPOINT sp_pull_batch")
            try:
                self._apply_collection(cursor, users_batch, self._apply_user_doc)
                self._apply_collection(cursor, reviews_batch, self._apply_review_doc)
                self._apply_collection(
                    cursor, merged_likes, self._apply_review_like_doc
                )
                self._apply_collection(
                    cursor, playlists_batch, self._apply_playlist_doc
                )
                self._apply_collection(
                    cursor, batches["playlist_images"], self._apply_playlist_image_doc
                )
                self._apply_collection(
                    cursor, playlist_tracks_batch, self._apply_playlist_track_doc
                )
                self._apply_collection(
                    cursor, interactions_batch, self._apply_interaction_doc
                )
            except Exception:
                cursor.execute("ROLLBACK TO SAVEPOINT sp_pull_batch")
                cursor.execute("RELEASE SAVEPOINT sp_pull_batch")
                self._reload_tombstones_from_db(cursor)
                raise
            cursor.execute("RELEASE SAVEPOINT sp_pull_batch")
            self._advance_watermarks(batches)

    def _apply_collection(
        self,
        cursor: sqlite3.Cursor,
        docs: list[dict[str, Any]],
        handler: Callable[[sqlite3.Cursor, Mapping[str, Any]], None],
    ) -> None:
        for idx, doc in enumerate(docs):
            sp_name = f"sp_doc_{idx}"
            cursor.execute(f"SAVEPOINT {sp_name}")
            try:
                handler(cursor, doc)
            except Exception as exc:  # noqa: BLE001
                cursor.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                self._reload_tombstones_from_db(cursor)
                logger.warning(
                    "Skipping Firestore doc %s due to apply error: %s", sp_name, exc
                )
            finally:
                cursor.execute(f"RELEASE SAVEPOINT {sp_name}")

    def sync_all(self) -> None:
        """Performs full bidirectional sync on startup across all 7 collections."""
        if not self.pull_deltas(force=True):
            return
        self._safe_run("sync_all_push", self._push_all_local)

    @staticmethod
    def _remote_user_is_newer_than_tombstone(
        remote_user: Mapping[str, Any] | None, deleted_at: str
    ) -> bool:
        if remote_user is None or remote_user.get("is_deleted"):
            return False
        remote_created_dt = _parse_iso_utc(remote_user.get("created_at"))
        del_dt = _parse_iso_utc(deleted_at)
        return (
            remote_created_dt is not None
            and del_dt is not None
            and remote_created_dt > del_dt
        )

    def _push_pending_user_tombstones(self) -> None:
        rows = self.conn.execute(
            "SELECT email, deleted_at FROM _firestore_user_tombstones WHERE is_deleted = 1"
        ).fetchall()
        for row in rows:
            email = _norm_email(str(row["email"] or ""))
            deleted_at = str(row["deleted_at"] or "").strip()
            if not email or not deleted_at:
                continue
            doc_id = user_doc_id(email)
            remote_user = self._get_remote_doc("users", doc_id)
            if self._remote_user_is_newer_than_tombstone(remote_user, deleted_at):
                self._persist_user_tombstone_state(
                    None, email, deleted_at, is_deleted=False
                )
                continue
            effective_del_at = (
                self._extract_effective_deleted_at(email, remote_user) or deleted_at
            )
            if effective_del_at != deleted_at:
                self._persist_user_tombstone_state(
                    None, email, effective_del_at, is_deleted=True
                )
            self.client.upsert_document(
                "users",
                doc_id,
                {
                    "email": email,
                    "is_deleted": True,
                    "deleted_at": effective_del_at,
                    "updated_at": _utc_now_iso(),
                },
            )

    def _push_pending_playlist_tombstones(self) -> None:
        rows = self.conn.execute(
            "SELECT pl_key, user_email, created_at FROM _firestore_playlist_tombstones"
        ).fetchall()
        for row in rows:
            pl_key = str(row["pl_key"] or "").strip()
            email = _norm_email(str(row["user_email"] or ""))
            created_at = str(row["created_at"] or "").strip()
            if not pl_key or not email or not created_at:
                continue
            remote_pl = self._get_remote_doc("playlists", pl_key)
            if remote_pl is not None and remote_pl.get("is_deleted"):
                continue
            self.client.upsert_document(
                "playlists",
                pl_key,
                {
                    "sync_key": pl_key,
                    "user_email": email,
                    "created_at": created_at,
                    "is_deleted": True,
                    "updated_at": _utc_now_iso(),
                },
            )

    def _push_all_local(self) -> None:
        self._push_pending_user_tombstones()
        self._push_pending_playlist_tombstones()
        user_ids = [
            int(r["user_id"])
            for r in self.conn.execute(
                "SELECT user_id FROM users ORDER BY user_id ASC"
            ).fetchall()
        ]
        for uid in user_ids:
            self._push_user(uid)

        review_ids = [
            int(r["review_id"])
            for r in self.conn.execute(
                "SELECT review_id FROM reviews ORDER BY review_id ASC"
            ).fetchall()
        ]
        for rid in review_ids:
            self._push_review(rid)

        like_rows = self.conn.execute(
            "SELECT review_id, user_id FROM review_likes"
        ).fetchall()
        for lr in like_rows:
            self._push_review_like(int(lr["review_id"]), int(lr["user_id"]))

        pl_ids = [
            int(r["playlist_id"])
            for r in self.conn.execute(
                "SELECT playlist_id FROM playlists ORDER BY playlist_id ASC"
            ).fetchall()
        ]
        for pid in pl_ids:
            self._push_playlist(pid)

        img_ids = [
            int(r["playlist_id"])
            for r in self.conn.execute(
                "SELECT playlist_id FROM playlist_images"
            ).fetchall()
        ]
        for pid in img_ids:
            self._push_playlist_image(pid)

        int_rows = self.conn.execute(
            "SELECT user_id, track_id FROM interactions ORDER BY interaction_id ASC"
        ).fetchall()
        for ir in int_rows:
            self._push_interaction(
                int(ir["user_id"]), int(ir["track_id"]), is_deleted=False
            )

    # ------------------------------------------------------------------
    # SQLite entity resolvers & upserts
    # ------------------------------------------------------------------

    def _resolve_plan_id(self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]) -> int:
        plan_name = doc.get("plan_name")
        if plan_name:
            row = cursor.execute(
                "SELECT plan_id FROM plans WHERE lower(name) = ? LIMIT 1",
                (str(plan_name).strip().lower(),),
            ).fetchone()
            if row is not None:
                return int(row["plan_id"])
        raw_id = int(doc.get("plan_id") or 1)
        row = cursor.execute(
            "SELECT plan_id FROM plans WHERE plan_id = ?", (raw_id,)
        ).fetchone()
        if row is not None:
            return int(row["plan_id"])
        fallback = cursor.execute(
            "SELECT plan_id FROM plans ORDER BY plan_id ASC LIMIT 1"
        ).fetchone()
        return int(fallback["plan_id"]) if fallback is not None else 1

    def _find_local_user_id(self, cursor: sqlite3.Cursor, email: str) -> int | None:
        clean = _norm_email(email)
        if not clean:
            return None
        row = cursor.execute(
            "SELECT user_id FROM users WHERE lower(email) = ?", (clean,)
        ).fetchone()
        return int(row["user_id"]) if row is not None else None

    def _ensure_local_user(
        self,
        cursor: sqlite3.Cursor,
        email: str,
        display_name: str | None = None,
    ) -> int | None:
        clean = _norm_email(email)
        if not clean or clean in self._deleted_user_emails:
            return None
        existing_id = self._find_local_user_id(cursor, clean)
        if existing_id is not None:
            return existing_id
        plan_row = cursor.execute(
            "SELECT plan_id FROM plans ORDER BY plan_id ASC LIMIT 1"
        ).fetchone()
        plan_id = int(plan_row["plan_id"]) if plan_row is not None else 1
        name = (display_name or clean.split("@")[0] or "Ribbit User").strip()
        cur = cursor.execute(
            """
            INSERT INTO users (email, password_hash, display_name, plan_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean, _SYNC_PLACEHOLDER_HASH, name, plan_id, _utc_now_iso()),
        )
        return int(cur.lastrowid) if cur.lastrowid is not None else None

    def _find_local_track_id(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> sqlite3.Row | None:
        spotify_id = doc.get("track_spotify_id")
        if spotify_id:
            row = cursor.execute(
                "SELECT track_id, spotify_id, cover_url, itunes_preview_url FROM tracks WHERE spotify_id = ? LIMIT 1",
                (str(spotify_id).strip(),),
            ).fetchone()
            if row is not None:
                return row
        title = str(doc.get("track_title") or "").strip()
        artist = str(doc.get("track_artist") or "").strip()
        if not title or not artist:
            return None
        return cursor.execute(
            "SELECT track_id, spotify_id, cover_url, itunes_preview_url FROM tracks WHERE lower(title) = ? AND lower(artist) = ? LIMIT 1",
            (title.lower(), artist.lower()),
        ).fetchone()

    def _ensure_local_track(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> int | None:
        existing = self._find_local_track_id(cursor, doc)
        if existing is not None:
            track_id = int(existing["track_id"])
            self._enrich_existing_track(cursor, track_id, existing, doc)
            return track_id
        spotify_id = doc.get("track_spotify_id")
        title = str(doc.get("track_title") or "").strip()
        artist = str(doc.get("track_artist") or "").strip()
        if not title or not artist:
            return None
        duration = max(int(doc.get("track_duration_seconds") or 180), 1)
        cur = cursor.execute(
            """
            INSERT INTO tracks (
                spotify_id, title, artist, album, duration_seconds, genre,
                country, release_year, cover_url, itunes_preview_url,
                explicit, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                str(spotify_id).strip() if spotify_id else None,
                title,
                artist,
                doc.get("track_album"),
                duration,
                str(doc.get("track_genre") or "Pop"),
                doc.get("track_country"),
                doc.get("track_release_year"),
                doc.get("track_cover_url"),
                doc.get("track_preview_url"),
                1 if doc.get("track_explicit") else 0,
                _utc_now_iso(),
            ),
        )
        return int(cur.lastrowid) if cur.lastrowid is not None else None

    def _enrich_existing_track(
        self,
        cursor: sqlite3.Cursor,
        track_id: int,
        row: sqlite3.Row,
        doc: Mapping[str, Any],
    ) -> None:
        raw_sp = doc.get("track_spotify_id")
        clean_sp = str(raw_sp).strip() if raw_sp else None
        cover = doc.get("track_cover_url")
        preview = doc.get("track_preview_url")
        needs_sp = not row["spotify_id"] and clean_sp
        needs_cover = not row["cover_url"] and cover
        needs_preview = not row["itunes_preview_url"] and preview
        if needs_sp or needs_cover or needs_preview:
            cursor.execute(
                """
                UPDATE tracks
                SET spotify_id = COALESCE(spotify_id, ?),
                    cover_url = COALESCE(cover_url, ?),
                    itunes_preview_url = COALESCE(itunes_preview_url, ?)
                WHERE track_id = ?
                """,
                (clean_sp, cover, preview, track_id),
            )

    def _is_pre_deletion_child(
        self,
        cursor: sqlite3.Cursor,
        email: str,
        created_val: Any = None,
        updated_val: Any = None,
    ) -> bool:
        clean = _norm_email(email)
        if not clean:
            return False
        if clean in self._deleted_user_emails:
            return True
        cutoff_dt = _parse_iso_utc(self._user_deleted_at.get(clean))
        if cutoff_dt is None:
            return False
        user_row = cursor.execute(
            "SELECT created_at FROM users WHERE lower(email) = ? LIMIT 1",
            (clean,),
        ).fetchone()
        user_created_dt = (
            _parse_iso_utc(user_row["created_at"]) if user_row is not None else None
        )
        created_dt = _parse_iso_utc(created_val)
        if created_dt is not None:
            if created_dt <= cutoff_dt:
                return True
            return user_created_dt is not None and created_dt < user_created_dt
        updated_dt = _parse_iso_utc(updated_val)
        return updated_dt is not None and updated_dt <= cutoff_dt

    def _purge_stale_local_user_if_needed(
        self, cursor: sqlite3.Cursor, email: str, doc: Mapping[str, Any]
    ) -> sqlite3.Row | None:
        existing = cursor.execute(
            "SELECT user_id, created_at, password_hash FROM users WHERE lower(email) = ?",
            (email,),
        ).fetchone()
        if existing is None:
            return None
        deleted_raw = self._extract_effective_deleted_at(email, doc)
        cutoff_dt = _parse_iso_utc(deleted_raw)
        local_dt = _parse_iso_utc(existing["created_at"])
        if cutoff_dt is not None and local_dt is not None and local_dt <= cutoff_dt:
            cursor.execute(
                "DELETE FROM users WHERE user_id = ?", (int(existing["user_id"]),)
            )
            return None
        return existing

    def _delete_local_user_if_stale(
        self, cursor: sqlite3.Cursor, email: str, cutoff_raw: Any
    ) -> bool:
        existing = cursor.execute(
            "SELECT user_id, created_at FROM users WHERE lower(email) = ?",
            (email,),
        ).fetchone()
        if existing is None:
            return True
        local_dt = _parse_iso_utc(existing["created_at"])
        cutoff_dt = _parse_iso_utc(cutoff_raw)
        if local_dt is not None and cutoff_dt is not None and local_dt > cutoff_dt:
            return False
        cursor.execute(
            "DELETE FROM users WHERE user_id = ?", (int(existing["user_id"]),)
        )
        return True

    @staticmethod
    def _is_stale_active_user_doc(cutoff_raw: Any, doc: Mapping[str, Any]) -> bool:
        cutoff_dt = _parse_iso_utc(cutoff_raw)
        if cutoff_dt is None:
            return False
        doc_created_dt = _parse_iso_utc(doc.get("created_at"))
        if doc_created_dt is not None:
            return doc_created_dt <= cutoff_dt
        doc_updated_dt = _parse_iso_utc(doc.get("updated_at"))
        return doc_updated_dt is not None and doc_updated_dt <= cutoff_dt

    @staticmethod
    def _is_local_user_newer(
        existing: sqlite3.Row | None, doc: Mapping[str, Any]
    ) -> bool:
        if existing is None or existing["password_hash"] == _SYNC_PLACEHOLDER_HASH:
            return False
        local_dt = _parse_iso_utc(existing["created_at"])
        doc_dt = _parse_iso_utc(doc.get("created_at"))
        return local_dt is not None and doc_dt is not None and local_dt > doc_dt

    @staticmethod
    def _local_user_predates_cutoff(
        cursor: sqlite3.Cursor, email: str, cutoff_dt: datetime
    ) -> bool:
        row = cursor.execute(
            "SELECT created_at FROM users WHERE lower(email) = ?",
            (email,),
        ).fetchone()
        if row is None:
            return False
        local_dt = _parse_iso_utc(row["created_at"])
        return local_dt is not None and local_dt <= cutoff_dt

    def _resolve_free_plan_id(self, cursor: sqlite3.Cursor) -> int:
        row = cursor.execute(
            "SELECT plan_id FROM plans WHERE lower(name) = 'free' ORDER BY plan_id ASC LIMIT 1"
        ).fetchone()
        if row is not None:
            return int(row["plan_id"])
        fallback = cursor.execute(
            "SELECT plan_id FROM plans ORDER BY plan_id ASC LIMIT 1"
        ).fetchone()
        return int(fallback["plan_id"]) if fallback is not None else 1

    @staticmethod
    def _is_primary_link_stale(
        pri_cutoff_dt: datetime | None,
        local_pri_dt: datetime | None,
        doc_ts_dt: datetime | None,
        doc_pri_created_dt: datetime | None = None,
    ) -> bool:
        if (
            pri_cutoff_dt is not None
            and local_pri_dt is not None
            and local_pri_dt <= pri_cutoff_dt
        ):
            return True
        ref_dt = doc_pri_created_dt or doc_ts_dt
        if pri_cutoff_dt is not None and (ref_dt is None or ref_dt <= pri_cutoff_dt):
            return True
        return local_pri_dt is not None and (ref_dt is None or ref_dt < local_pri_dt)

    def _resolve_primary_user_id(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> int | None:
        raw_pri = doc.get("primary_user_email")
        if not raw_pri:
            return None
        pri_email = _norm_email(str(raw_pri))
        if not pri_email:
            return None
        with self._lock:
            is_deleted = pri_email in self._deleted_user_emails
            pri_cutoff_dt = _parse_iso_utc(self._user_deleted_at.get(pri_email))
        if is_deleted:
            return None
        local_pri = cursor.execute(
            "SELECT created_at, password_hash FROM users WHERE lower(email) = ?",
            (pri_email,),
        ).fetchone()
        local_pri_dt = (
            _parse_iso_utc(local_pri["created_at"])
            if local_pri is not None
            and local_pri["password_hash"] != _SYNC_PLACEHOLDER_HASH
            else None
        )
        doc_ts_dt = _parse_iso_utc(doc.get("updated_at") or doc.get("created_at"))
        doc_pri_created_dt = _parse_iso_utc(doc.get("primary_user_created_at"))
        if self._is_primary_link_stale(
            pri_cutoff_dt, local_pri_dt, doc_ts_dt, doc_pri_created_dt
        ):
            return None
        return self._ensure_local_user(cursor, pri_email)

    def _upsert_local_user(
        self,
        cursor: sqlite3.Cursor,
        existing: sqlite3.Row | None,
        email: str,
        doc: Mapping[str, Any],
        fields: tuple[Any, ...],
    ) -> None:
        if self._is_local_user_newer(existing, doc):
            return
        doc_created_at = str(doc["created_at"]) if doc.get("created_at") else None
        if existing is not None:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = ?,
                    spotify_id = COALESCE(?, spotify_id),
                    spotify_premium = ?,
                    display_name = ?,
                    age = ?,
                    plan_id = ?,
                    primary_account_id = ?,
                    blocked_genres = ?,
                    favorite_genres = ?,
                    preferred_theme = ?,
                    is_admin = ?,
                    created_at = COALESCE(?, created_at),
                    birth_date = ?
                WHERE user_id = ?
                """,
                (*fields[:11], doc_created_at, fields[11], int(existing["user_id"])),
            )
            return
        cursor.execute(
            """
            INSERT INTO users (
                email, password_hash, spotify_id, spotify_premium,
                display_name, age, plan_id, primary_account_id,
                blocked_genres, favorite_genres, preferred_theme,
                is_admin, created_at, birth_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                *fields[:11],
                doc_created_at or _utc_now_iso(),
                fields[11],
            ),
        )

    def _build_user_fields(
        self, cursor: sqlite3.Cursor, email: str, doc: Mapping[str, Any]
    ) -> tuple[Any, ...]:
        primary_id = self._resolve_primary_user_id(cursor, doc)
        if doc.get("primary_user_email") and primary_id is None:
            plan_id = self._resolve_free_plan_id(cursor)
        else:
            plan_id = self._resolve_plan_id(cursor, doc)
        raw_sp_id = doc.get("spotify_id")
        spotify_id = str(raw_sp_id).strip() if raw_sp_id else None
        if spotify_id:
            cursor.execute(
                "UPDATE users SET spotify_id = NULL WHERE spotify_id = ? AND lower(email) != ?",
                (spotify_id, email),
            )
        return (
            str(doc.get("password_hash") or "!synced"),
            spotify_id,
            1 if doc.get("spotify_premium") else 0,
            str(doc.get("display_name") or email.split("@", maxsplit=1)[0]),
            doc.get("age"),
            plan_id,
            primary_id,
            doc.get("blocked_genres"),
            doc.get("favorite_genres"),
            str(doc.get("preferred_theme") or "dark"),
            1 if doc.get("is_admin") else 0,
            doc.get("birth_date"),
        )

    def _apply_user_doc(self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]) -> None:
        raw_email = str(doc.get("email") or "").strip()
        if not raw_email:
            return
        email = _norm_email(raw_email)
        if doc.get("is_deleted"):
            deleted_at = str(
                doc.get("deleted_at") or doc.get("updated_at") or _utc_now_iso()
            )
            was_stale = self._delete_local_user_if_stale(cursor, email, deleted_at)
            self._persist_user_tombstone_state(
                cursor, email, deleted_at, is_deleted=was_stale
            )
            return
        cutoff_raw = self._extract_effective_deleted_at(email, doc)
        if self._is_stale_active_user_doc(cutoff_raw, doc):
            was_stale = self._delete_local_user_if_stale(cursor, email, cutoff_raw)
            if cutoff_raw:
                self._persist_user_tombstone_state(
                    cursor, email, str(cutoff_raw), is_deleted=was_stale
                )
            return
        existing = self._purge_stale_local_user_if_needed(cursor, email, doc)
        if not self._is_local_user_newer(existing, doc):
            fields = self._build_user_fields(cursor, email, doc)
            self._upsert_local_user(cursor, existing, email, doc, fields)
        if cutoff_raw or email in self._deleted_user_emails:
            self._persist_user_tombstone_state(
                cursor, email, str(cutoff_raw or ""), is_deleted=False
            )

    def _reconcile_review_likes_count(
        self,
        cursor: sqlite3.Cursor,
        review_id: int,
        synced_likes_count: int = 0,
    ) -> None:
        count_row = cursor.execute(
            "SELECT COUNT(*) FROM review_likes WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        actual_likes = int(count_row[0]) if count_row is not None else 0
        target_likes = max(actual_likes, synced_likes_count)
        cursor.execute(
            "UPDATE reviews SET likes_count = MAX(likes_count, ?) WHERE review_id = ?",
            (target_likes, review_id),
        )

    def _apply_review_doc(self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]) -> None:
        email = str(doc.get("user_email") or "").strip()
        if not email or self._is_pre_deletion_child(
            cursor, email, doc.get("created_at"), doc.get("updated_at")
        ):
            return
        is_deleted = 1 if doc.get("is_deleted") else 0
        if is_deleted:
            user_id = self._find_local_user_id(cursor, email)
            track_row = self._find_local_track_id(cursor, doc)
            track_id = int(track_row["track_id"]) if track_row is not None else None
        else:
            user_id = self._ensure_local_user(cursor, email, doc.get("author_name"))
            track_id = self._ensure_local_track(cursor, doc)
        if user_id is None or track_id is None:
            return

        created_at = str(doc.get("created_at") or _utc_now_iso())
        rating = max(1, min(5, int(doc.get("rating") or 5)))
        likes_count = max(0, int(doc.get("likes_count") or 0))
        text = doc.get("text")

        existing = cursor.execute(
            """
            SELECT review_id, is_deleted FROM reviews
            WHERE user_id = ? AND track_id = ? AND created_at = ?
            LIMIT 1
            """,
            (user_id, track_id, created_at),
        ).fetchone()
        if existing is not None:
            review_id = int(existing["review_id"])
            effective_deleted = 1 if (is_deleted or int(existing["is_deleted"])) else 0
            if not effective_deleted:
                cursor.execute(
                    """
                    UPDATE reviews
                    SET is_deleted = 1
                    WHERE user_id = ? AND track_id = ? AND is_deleted = 0 AND review_id != ?
                    """,
                    (user_id, track_id, review_id),
                )
            cursor.execute(
                """
                UPDATE reviews
                SET rating = ?, text = ?, likes_count = ?, is_deleted = ?
                WHERE review_id = ?
                """,
                (rating, text, likes_count, effective_deleted, review_id),
            )
            self._reconcile_review_likes_count(cursor, review_id, likes_count)
            return

        if not is_deleted:
            cursor.execute(
                """
                UPDATE reviews
                SET is_deleted = 1
                WHERE user_id = ? AND track_id = ? AND is_deleted = 0
                """,
                (user_id, track_id),
            )

        cur = cursor.execute(
            """
            INSERT INTO reviews (
                user_id, track_id, rating, text, likes_count, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, track_id, rating, text, likes_count, is_deleted, created_at),
        )
        if cur.lastrowid is not None:
            self._reconcile_review_likes_count(cursor, int(cur.lastrowid), likes_count)

    def _has_deleted_like_actor(self, liker_email: str, rev_email: str) -> bool:
        return (
            _norm_email(liker_email) in self._deleted_user_emails
            or _norm_email(rev_email) in self._deleted_user_emails
        )

    def _clear_pending_like(self, like_key: str) -> None:
        with self._lock:
            self._pending_review_likes.pop(like_key, None)
            self._pending_like_attempts.pop(like_key, None)

    def _defer_pending_like(self, like_key: str, doc: Mapping[str, Any]) -> None:
        with self._lock:
            attempts = self._pending_like_attempts.get(like_key, 0) + 1
            if attempts < _MAX_PENDING_LIKE_ATTEMPTS:
                self._pending_like_attempts[like_key] = attempts
                self._pending_review_likes[like_key] = dict(doc)
                return
            self._clear_pending_like(like_key)
            self._exhausted_review_likes[like_key] = str(doc.get("updated_at") or "")
            if len(self._exhausted_review_likes) > 256:
                self._exhausted_review_likes.pop(
                    next(iter(self._exhausted_review_likes))
                )

    def _is_exhausted_pending_like(self, like_key: str, doc: Mapping[str, Any]) -> bool:
        with self._lock:
            exhausted_ts = self._exhausted_review_likes.get(like_key)
            if exhausted_ts is None:
                return False
            if str(doc.get("updated_at") or "") <= exhausted_ts:
                return True
            self._exhausted_review_likes.pop(like_key, None)
            return False

    def _is_deleted_like_doc(
        self,
        cursor: sqlite3.Cursor,
        liker_email: str,
        rev_email: str,
        doc: Mapping[str, Any],
    ) -> bool:
        return (
            self._has_deleted_like_actor(liker_email, rev_email)
            or self._is_pre_deletion_child(
                cursor, liker_email, doc.get("created_at"), doc.get("updated_at")
            )
            or self._is_pre_deletion_child(
                cursor,
                rev_email,
                doc.get("review_created_at") or doc.get("created_at"),
                doc.get("updated_at"),
            )
        )

    def _resolve_review_id_for_like(
        self, cursor: sqlite3.Cursor, rev_email: str, doc: Mapping[str, Any]
    ) -> int | None:
        author_id = self._find_local_user_id(cursor, rev_email)
        track_row = self._find_local_track_id(cursor, doc)
        if author_id is None or track_row is None:
            return None
        rev_created_at = str(doc.get("review_created_at") or "").strip()
        rev_row = cursor.execute(
            """
            SELECT review_id FROM reviews
            WHERE user_id = ? AND track_id = ?
              AND (? = '' OR created_at = ?)
            ORDER BY review_id DESC LIMIT 1
            """,
            (author_id, int(track_row["track_id"]), rev_created_at, rev_created_at),
        ).fetchone()
        return int(rev_row["review_id"]) if rev_row is not None else None

    def _apply_review_like_doc(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> None:
        liker_email = str(doc.get("user_email") or "").strip()
        rev_email = str(doc.get("review_user_email") or "").strip()
        if not liker_email or not rev_email:
            return
        like_key = _pending_like_key(doc)
        if self._is_deleted_like_doc(cursor, liker_email, rev_email, doc):
            with self._lock:
                self._exhausted_review_likes.pop(like_key, None)
            self._clear_pending_like(like_key)
            return
        review_id = self._resolve_review_id_for_like(cursor, rev_email, doc)
        liker_id = (
            self._ensure_local_user(cursor, liker_email)
            if review_id is not None
            else None
        )
        if review_id is None or liker_id is None:
            if not self._is_exhausted_pending_like(like_key, doc):
                self._defer_pending_like(like_key, doc)
            return
        cursor.execute(
            """
            INSERT OR IGNORE INTO review_likes (review_id, user_id, created_at)
            VALUES (?, ?, ?)
            """,
            (
                review_id,
                liker_id,
                str(doc.get("created_at") or _utc_now_iso()),
            ),
        )
        with self._lock:
            self._exhausted_review_likes.pop(like_key, None)
        self._clear_pending_like(like_key)
        self._reconcile_review_likes_count(cursor, review_id)

    def _resolve_local_playlist_id(
        self,
        cursor: sqlite3.Cursor,
        user_email: str,
        created_at: str,
    ) -> int | None:
        user_id = self._find_local_user_id(cursor, user_email)
        if user_id is None or not created_at:
            return None
        row = cursor.execute(
            """
            SELECT playlist_id FROM playlists
            WHERE user_id = ? AND created_at = ?
            LIMIT 1
            """,
            (user_id, created_at),
        ).fetchone()
        return int(row["playlist_id"]) if row is not None else None

    def _resolve_source_playlist_id(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> int | None:
        src_email = str(doc.get("source_playlist_user_email") or "").strip()
        src_created = str(doc.get("source_playlist_created_at") or "").strip()
        if not src_email or not src_created:
            return None
        return self._resolve_local_playlist_id(cursor, src_email, src_created)

    def _resolve_updated_cover_url(
        self,
        cursor: sqlite3.Cursor,
        local_pid: int,
        current_cover_url: Any,
        remote_cover_url: Any,
    ) -> str | None:
        normalized = _normalize_local_cover_url(remote_cover_url, local_pid)
        if normalized is not None:
            return normalized
        img_row = cursor.execute(
            "SELECT length(image_data) AS sz FROM playlist_images WHERE playlist_id = ?",
            (local_pid,),
        ).fetchone()
        if img_row is not None and int(img_row["sz"] or 0) > _MAX_IMAGE_BYTES:
            return str(current_cover_url) if current_cover_url is not None else None
        return None

    def _handle_deleted_playlist_doc(
        self,
        cursor: sqlite3.Cursor,
        email: str,
        created_at: str,
        doc: Mapping[str, Any],
    ) -> bool:
        pl_key = playlist_doc_id(email, created_at)
        with self._lock:
            locally_deleted = pl_key in self._deleted_playlist_keys
        if not doc.get("is_deleted") and not locally_deleted:
            return False
        if doc.get("is_deleted"):
            self._persist_playlist_tombstone(
                cursor,
                pl_key,
                email,
                created_at,
                str(doc.get("updated_at") or _utc_now_iso()),
            )
        user_id = self._find_local_user_id(cursor, email)
        if user_id is not None:
            cursor.execute(
                "DELETE FROM playlists WHERE user_id = ? AND created_at = ?",
                (user_id, created_at),
            )
        return True

    def _apply_playlist_doc(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> None:
        email = str(doc.get("user_email") or "").strip()
        created_at = str(doc.get("created_at") or "").strip()
        if (
            not email
            or not created_at
            or self._is_pre_deletion_child(
                cursor, email, created_at, doc.get("updated_at")
            )
        ):
            return
        if self._handle_deleted_playlist_doc(cursor, email, created_at, doc):
            return
        user_id = self._ensure_local_user(cursor, email)
        if user_id is None:
            return
        existing = cursor.execute(
            "SELECT playlist_id, cover_image_url FROM playlists WHERE user_id = ? AND created_at = ? LIMIT 1",
            (user_id, created_at),
        ).fetchone()

        source_playlist_id = self._resolve_source_playlist_id(cursor, doc)
        name = str(doc.get("name") or "Playlist")
        if existing is not None:
            local_pid = int(existing["playlist_id"])
            cover_url = self._resolve_updated_cover_url(
                cursor,
                local_pid,
                existing["cover_image_url"],
                doc.get("cover_image_url"),
            )
            cursor.execute(
                """
                UPDATE playlists
                SET name = ?,
                    description = ?,
                    spotify_playlist_id = ?,
                    is_exported = ?,
                    max_duration_seconds = ?,
                    deck_filters = ?,
                    cover_image_url = ?,
                    source_playlist_id = ?
                WHERE playlist_id = ?
                """,
                (
                    name,
                    doc.get("description"),
                    doc.get("spotify_playlist_id"),
                    1 if doc.get("is_exported") else 0,
                    doc.get("max_duration_seconds"),
                    doc.get("deck_filters"),
                    cover_url,
                    source_playlist_id,
                    local_pid,
                ),
            )
            return

        cur = cursor.execute(
            """
            INSERT INTO playlists (
                user_id, name, description, spotify_playlist_id, is_exported,
                created_at, max_duration_seconds, deck_filters, cover_image_url,
                source_playlist_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name,
                doc.get("description"),
                doc.get("spotify_playlist_id"),
                1 if doc.get("is_exported") else 0,
                created_at,
                doc.get("max_duration_seconds"),
                doc.get("deck_filters"),
                None,
                source_playlist_id,
            ),
        )
        new_pid = cur.lastrowid
        if new_pid is not None:
            local_cover_url = _normalize_local_cover_url(
                doc.get("cover_image_url"), int(new_pid)
            )
            if local_cover_url is not None:
                cursor.execute(
                    "UPDATE playlists SET cover_image_url = ? WHERE playlist_id = ?",
                    (local_cover_url, int(new_pid)),
                )

    def _apply_playlist_image_doc(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> None:
        email = str(doc.get("user_email") or "").strip()
        pl_created = str(doc.get("playlist_created_at") or "").strip()
        b64_data = doc.get("image_data_b64")
        if (
            not email
            or not pl_created
            or not b64_data
            or self._is_pre_deletion_child(
                cursor, email, pl_created, doc.get("updated_at")
            )
        ):
            return
        playlist_id = self._resolve_local_playlist_id(cursor, email, pl_created)
        if playlist_id is None:
            return
        raw_bytes = base64.b64decode(str(b64_data))
        cursor.execute(
            """
            INSERT INTO playlist_images (playlist_id, content_type, image_data, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(playlist_id) DO UPDATE SET
                content_type = excluded.content_type,
                image_data = excluded.image_data,
                updated_at = excluded.updated_at
            """,
            (
                playlist_id,
                str(doc.get("content_type") or "image/jpeg"),
                raw_bytes,
                str(doc.get("updated_at") or _utc_now_iso()),
            ),
        )
        cursor.execute(
            """
            UPDATE playlists
            SET cover_image_url = COALESCE(cover_image_url, ?)
            WHERE playlist_id = ?
            """,
            (f"/api/playlists/{playlist_id}/image", playlist_id),
        )

    def _apply_playlist_track_doc(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> None:
        email = str(doc.get("user_email") or "").strip()
        pl_created = str(doc.get("playlist_created_at") or "").strip()
        if (
            not email
            or not pl_created
            or self._is_pre_deletion_child(
                cursor, email, pl_created, doc.get("updated_at")
            )
        ):
            return
        playlist_id = self._resolve_local_playlist_id(cursor, email, pl_created)
        if playlist_id is None:
            return
        if doc.get("is_removed"):
            track_row = self._find_local_track_id(cursor, doc)
            if track_row is not None:
                cursor.execute(
                    "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                    (playlist_id, int(track_row["track_id"])),
                )
            return
        track_id = self._ensure_local_track(cursor, doc)
        if track_id is None:
            return
        cursor.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        cursor.execute(
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, added_at)
            VALUES (?, ?, ?)
            """,
            (playlist_id, track_id, str(doc.get("added_at") or _utc_now_iso())),
        )

    def _apply_interaction_doc(
        self, cursor: sqlite3.Cursor, doc: Mapping[str, Any]
    ) -> None:
        email = str(doc.get("user_email") or "").strip()
        if not email or self._is_pre_deletion_child(
            cursor, email, doc.get("created_at"), doc.get("updated_at")
        ):
            return
        if doc.get("is_deleted"):
            user_id = self._find_local_user_id(cursor, email)
            track_row = self._find_local_track_id(cursor, doc)
            if user_id is not None and track_row is not None:
                cursor.execute(
                    "DELETE FROM interactions WHERE user_id = ? AND track_id = ?",
                    (user_id, int(track_row["track_id"])),
                )
            return
        user_id = self._ensure_local_user(cursor, email)
        track_id = self._ensure_local_track(cursor, doc)
        if user_id is None or track_id is None:
            return
        action = str(doc.get("action") or "").strip()
        if not action:
            return
        cursor.execute(
            """
            INSERT INTO interactions (user_id, track_id, action, created_at, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, track_id) DO UPDATE SET
                action = excluded.action,
                created_at = excluded.created_at,
                source = excluded.source
            """,
            (
                user_id,
                track_id,
                action,
                str(doc.get("created_at") or _utc_now_iso()),
                doc.get("source"),
            ),
        )


__all__ = [
    "FirestoreSyncService",
    "playlist_doc_id",
    "review_doc_id",
    "track_sync_key",
    "user_doc_id",
]
