"""SQLite implementation of the track access repository port."""

from datetime import UTC, datetime
from typing import Any
lazy import sqlite3

from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
from app.domain.models.track_access import (
    AdminTrackAccessEntry,
    TrackAccess,
    TrackAccessCount,
    TrackAccessEntry,
)
from app.infrastructure.repositories.connection import transaction


def _row_to_entry(row: sqlite3.Row) -> TrackAccessEntry:
    return TrackAccessEntry(
        access_id=int(row["access_id"]),
        user_id=int(row["user_id"]),
        track_id=int(row["track_id"]),
        track_title=str(row["track_title"]),
        track_artist=str(row["track_artist"]),
        track_genre=str(row["track_genre"]),
        track_album=row["track_album"],
        track_duration_seconds=int(row["track_duration_seconds"] or 0),
        track_cover_url=row["track_cover_url"],
        track_preview_url=row["track_preview_url"],
        track_explicit=bool(row["track_explicit"]),
        track_is_deleted=bool(row["track_is_deleted"]),
        source=str(row["source"]),
        accessed_at=datetime.fromisoformat(str(row["accessed_at"])),
    )


def _row_to_admin_entry(row: sqlite3.Row) -> AdminTrackAccessEntry:
    return AdminTrackAccessEntry(
        access_id=int(row["access_id"]),
        user_id=int(row["user_id"]),
        user_display_name=str(row["user_display_name"]),
        user_email=str(row["user_email"]),
        track_id=int(row["track_id"]),
        track_title=str(row["track_title"]),
        track_artist=str(row["track_artist"]),
        track_genre=str(row["track_genre"]),
        track_is_deleted=bool(row["track_is_deleted"]),
        source=str(row["source"]),
        accessed_at=datetime.fromisoformat(str(row["accessed_at"])),
    )


class SQLiteTrackAccessRepository(TrackAccessRepositoryPort):
    """SQLite adapter implementing TrackAccessRepositoryPort."""

    def __init__(
        self, conn: sqlite3.Connection, sync_service: Any | None = None
    ) -> None:
        self.conn = conn
        self._sync = sync_service

    def _pull_deltas(self) -> None:
        if self._sync is not None:
            self._sync.pull_deltas()

    def record(self, access: TrackAccess) -> TrackAccess:
        self._pull_deltas()
        accessed_at = access.accessed_at or datetime.now(UTC)
        accessed_at_str = accessed_at.isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO track_accesses (user_id, track_id, source, accessed_at)
                VALUES (?, ?, ?, ?)
                """,
                (access.user_id, access.track_id, str(access.source), accessed_at_str),
            )
            access_id = cursor.lastrowid
            if self._sync is not None and access_id is not None:
                self._sync.push_track_access_by_id(access_id)
        return TrackAccess(
            access_id=access_id,
            user_id=access.user_id,
            track_id=access.track_id,
            source=access.source,
            accessed_at=accessed_at,
        )

    def list_by_user(
        self,
        user_id: int,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TrackAccessEntry]:
        self._pull_deltas()
        rows = self.conn.execute(
            """
            SELECT
                ta.access_id,
                ta.user_id,
                ta.track_id,
                ta.source,
                ta.accessed_at,
                t.title AS track_title,
                t.artist AS track_artist,
                t.genre AS track_genre,
                NULL AS track_album,
                t.duration_seconds AS track_duration_seconds,
                t.cover_url AS track_cover_url,
                t.itunes_preview_url AS track_preview_url,
                t.explicit AS track_explicit,
                t.is_deleted AS track_is_deleted
            FROM track_accesses ta
            INNER JOIN tracks t ON t.track_id = ta.track_id
            WHERE ta.user_id = ?
              AND (? = 1 OR t.is_deleted = 0)
            ORDER BY ta.accessed_at DESC, ta.access_id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, int(include_deleted), limit, offset),
        ).fetchall()
        return [_row_to_entry(row) for row in rows]

    def list_seen_track_ids(self, user_id: int) -> list[int]:
        self._pull_deltas()
        rows = self.conn.execute(
            """
            SELECT DISTINCT ta.track_id AS track_id
            FROM track_accesses ta
            INNER JOIN tracks t ON t.track_id = ta.track_id
            WHERE ta.user_id = ? AND t.is_deleted = 0
            UNION
            SELECT DISTINCT i.track_id AS track_id
            FROM interactions i
            INNER JOIN tracks t ON t.track_id = i.track_id
            WHERE i.user_id = ? AND t.is_deleted = 0
            ORDER BY track_id ASC
            """,
            (user_id, user_id),
        ).fetchall()
        return [int(row["track_id"]) for row in rows]

    def list_all_admin(
        self,
        *,
        user_id: int | None = None,
        track_id: int | None = None,
        only_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminTrackAccessEntry]:
        self._pull_deltas()
        rows = self.conn.execute(
            """
            SELECT
                ta.access_id,
                ta.user_id,
                u.display_name AS user_display_name,
                u.email AS user_email,
                ta.track_id,
                t.title AS track_title,
                t.artist AS track_artist,
                t.genre AS track_genre,
                t.is_deleted AS track_is_deleted,
                ta.source,
                ta.accessed_at
            FROM track_accesses ta
            INNER JOIN users u ON u.user_id = ta.user_id
            INNER JOIN tracks t ON t.track_id = ta.track_id
            WHERE (? IS NULL OR ta.user_id = ?)
              AND (? IS NULL OR ta.track_id = ?)
              AND (? = 0 OR t.is_deleted = 1)
            ORDER BY ta.accessed_at DESC, ta.access_id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, user_id, track_id, track_id, int(only_deleted), limit, offset),
        ).fetchall()
        return [_row_to_admin_entry(row) for row in rows]

    def count_all(self) -> int:
        self._pull_deltas()
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM track_accesses"
        ).fetchone()
        return int(row["total"]) if row else 0

    def count_by_track(
        self, limit: int = 10, include_deleted: bool = True
    ) -> list[TrackAccessCount]:
        self._pull_deltas()
        rows = self.conn.execute(
            """
            SELECT
                t.track_id AS track_id,
                t.title AS label,
                t.artist AS artist,
                t.is_deleted AS is_deleted,
                COUNT(*) AS access_count
            FROM track_accesses ta
            INNER JOIN tracks t ON t.track_id = ta.track_id
            WHERE (? = 1 OR t.is_deleted = 0)
            GROUP BY t.track_id, t.title, t.artist, t.is_deleted
            ORDER BY access_count DESC, t.track_id ASC
            LIMIT ?
            """,
            (int(include_deleted), limit),
        ).fetchall()
        return [
            TrackAccessCount(
                track_id=int(row["track_id"]),
                label=str(row["label"]),
                artist=str(row["artist"]),
                is_deleted=bool(row["is_deleted"]),
                access_count=int(row["access_count"]),
            )
            for row in rows
        ]

    def count_by_genre(self, include_deleted: bool = True) -> list[TrackAccessCount]:
        self._pull_deltas()
        rows = self.conn.execute(
            """
            SELECT
                t.genre AS label,
                COUNT(*) AS access_count
            FROM track_accesses ta
            INNER JOIN tracks t ON t.track_id = ta.track_id
            WHERE (? = 1 OR t.is_deleted = 0)
            GROUP BY t.genre
            ORDER BY access_count DESC, t.genre ASC
            """,
            (int(include_deleted),),
        ).fetchall()
        return [
            TrackAccessCount(
                label=str(row["label"]),
                access_count=int(row["access_count"]),
            )
            for row in rows
        ]


TrackAccessRepository = SQLiteTrackAccessRepository
