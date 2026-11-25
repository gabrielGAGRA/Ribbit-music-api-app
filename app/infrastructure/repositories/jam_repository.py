"""SQLite implementation of the Jam session and queue persistence port."""

from datetime import UTC, datetime
from typing import Any
lazy import sqlite3

from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.jam import Jam, JamQueueItem
from app.infrastructure.repositories.connection import transaction


def _row_to_jam(row: sqlite3.Row) -> Jam:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    keys = row.keys()
    duration_minutes = row["duration_minutes"] if "duration_minutes" in keys else 60
    max_superlikes = row["max_superlikes"] if "max_superlikes" in keys else 10
    superlikes_used = row["superlikes_used"] if "superlikes_used" in keys else 0
    skip_votes_threshold = (
        row["skip_votes_threshold"] if "skip_votes_threshold" in keys else 3
    )
    accumulated_duration_seconds = (
        row["accumulated_duration_seconds"]
        if "accumulated_duration_seconds" in keys
        else 0
    )
    deck_source = row["deck_source"] if "deck_source" in keys else "free"
    source_playlist_id = (
        row["source_playlist_id"] if "source_playlist_id" in keys else None
    )
    return Jam(
        jam_id=row["jam_id"],
        host_user_id=row["host_user_id"],
        room_name=row["room_name"],
        room_code=row["room_code"],
        is_active=bool(row["is_active"]),
        current_track_id=row["current_track_id"],
        created_at=created_at,
        duration_minutes=duration_minutes,
        max_superlikes=max_superlikes,
        superlikes_used=superlikes_used,
        skip_votes_threshold=skip_votes_threshold,
        accumulated_duration_seconds=accumulated_duration_seconds,
        deck_source=deck_source,
        source_playlist_id=source_playlist_id,
    )


def _row_to_queue_item(row: sqlite3.Row) -> JamQueueItem:
    added_at = datetime.fromisoformat(row["added_at"]) if row["added_at"] else None
    return JamQueueItem(
        jam_queue_id=row["jam_queue_id"],
        jam_id=row["jam_id"],
        track_id=row["track_id"],
        initial_vote_points=int(row["vote_points"]),
        added_at=added_at,
    )


class SQLiteJamRepository(JamRepositoryPort):
    """SQLite adapter implementing JamRepositoryPort."""

    def __init__(
        self, conn: sqlite3.Connection, sync_service: Any | None = None
    ) -> None:
        self.conn = conn
        self._sync = sync_service

    def _pull_deltas(self) -> None:
        if self._sync is not None:
            self._sync.pull_deltas()

    def _push_jam(self, jam_id: int) -> None:
        if self._sync is not None:
            self._sync.push_jam_by_id(jam_id)

    def find_by_id(self, jam_id: int) -> Jam | None:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM jams WHERE jam_id = ?",
            (jam_id,),
        )
        row = cursor.fetchone()
        return _row_to_jam(row) if row else None

    def find_by_code(self, room_code: str) -> Jam | None:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM jams WHERE room_code = ? AND is_active = 1",
            (room_code,),
        )
        row = cursor.fetchone()
        return _row_to_jam(row) if row else None

    def save(self, jam: Jam) -> Jam:
        self._pull_deltas()
        target_id: int | None = jam.jam_id
        with transaction(self.conn) as cursor:
            if jam.jam_id is not None:
                existing = cursor.execute(
                    "SELECT jam_id FROM jams WHERE jam_id = ?",
                    (jam.jam_id,),
                ).fetchone()
                if not existing:
                    raise EntityNotFoundError(entity_name="Jam", entity_id=jam.jam_id)
                cursor.execute(
                    """
                    UPDATE jams
                    SET host_user_id = ?,
                        room_name = ?,
                        room_code = ?,
                        is_active = ?,
                        current_track_id = ?,
                        duration_minutes = ?,
                        max_superlikes = ?,
                        superlikes_used = ?,
                        skip_votes_threshold = ?,
                        accumulated_duration_seconds = ?,
                        deck_source = ?,
                        source_playlist_id = ?
                    WHERE jam_id = ?
                    """,
                    (
                        jam.host_user_id,
                        jam.room_name,
                        jam.room_code,
                        1 if jam.is_active else 0,
                        jam.current_track_id,
                        jam.duration_minutes,
                        jam.max_superlikes,
                        jam.superlikes_used,
                        jam.skip_votes_threshold,
                        jam.accumulated_duration_seconds,
                        jam.deck_source,
                        jam.source_playlist_id,
                        jam.jam_id,
                    ),
                )
                self._push_jam(jam.jam_id)
            else:
                created_at_str = (jam.created_at or datetime.now(UTC)).isoformat()
                cursor.execute(
                    """
                    INSERT INTO jams (
                        host_user_id, room_name, room_code, is_active, current_track_id, created_at,
                        duration_minutes, max_superlikes, superlikes_used, skip_votes_threshold,
                        accumulated_duration_seconds, deck_source, source_playlist_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        jam.host_user_id,
                        jam.room_name,
                        jam.room_code,
                        1 if jam.is_active else 0,
                        jam.current_track_id,
                        created_at_str,
                        jam.duration_minutes,
                        jam.max_superlikes,
                        jam.superlikes_used,
                        jam.skip_votes_threshold,
                        jam.accumulated_duration_seconds,
                        jam.deck_source,
                        jam.source_playlist_id,
                    ),
                )
                target_id = cursor.lastrowid
                if target_id is not None:
                    self._push_jam(target_id)
        if target_id is not None:
            return self.find_by_id(target_id) or jam
        return jam

    def find_queue_item(self, jam_id: int, track_id: int) -> JamQueueItem | None:
        self._pull_deltas()
        cursor = self.conn.execute(
            """
            SELECT * FROM jam_queue_items
            WHERE jam_id = ? AND track_id = ?
            """,
            (jam_id, track_id),
        )
        row = cursor.fetchone()
        return _row_to_queue_item(row) if row else None

    def save_queue_item(self, item: JamQueueItem) -> JamQueueItem:
        self._pull_deltas()
        with transaction(self.conn) as cursor:
            existing = cursor.execute(
                """
                SELECT jam_queue_id FROM jam_queue_items
                WHERE jam_id = ? AND track_id = ?
                """,
                (item.jam_id, item.track_id),
            ).fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE jam_queue_items
                    SET vote_points = ?
                    WHERE jam_id = ? AND track_id = ?
                    """,
                    (item.vote_points, item.jam_id, item.track_id),
                )
            else:
                added_at_str = (item.added_at or datetime.now(UTC)).isoformat()
                cursor.execute(
                    """
                    INSERT INTO jam_queue_items (jam_id, track_id, vote_points, added_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (item.jam_id, item.track_id, item.vote_points, added_at_str),
                )
            self._push_jam(item.jam_id)
        return self.find_queue_item(item.jam_id, item.track_id) or item

    def list_queue(self, jam_id: int) -> list[JamQueueItem]:
        self._pull_deltas()
        cursor = self.conn.execute(
            """
            SELECT * FROM jam_queue_items
            WHERE jam_id = ?
            ORDER BY vote_points DESC, added_at ASC
            """,
            (jam_id,),
        )
        rows = cursor.fetchall()
        return [_row_to_queue_item(r) for r in rows]

    def remove_track_from_queue(self, jam_id: int, track_id: int) -> bool:
        self._pull_deltas()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                DELETE FROM jam_queue_items
                WHERE jam_id = ? AND track_id = ?
                """,
                (jam_id, track_id),
            )
            removed = cursor.rowcount > 0
            if removed:
                self._push_jam(jam_id)
        return removed

    def advance_playback(
        self, jam_id: int, new_track_id: int, removed_track_id: int
    ) -> Jam:
        self._pull_deltas()
        with transaction(self.conn) as cursor:
            row = cursor.execute(
                "SELECT jam_id FROM jams WHERE jam_id = ?",
                (jam_id,),
            ).fetchone()
            if not row:
                raise EntityNotFoundError(entity_name="Jam", entity_id=jam_id)

            cursor.execute(
                """
                UPDATE jams
                SET current_track_id = ?
                WHERE jam_id = ?
                """,
                (new_track_id, jam_id),
            )
            cursor.execute(
                """
                DELETE FROM jam_queue_items
                WHERE jam_id = ? AND track_id = ?
                """,
                (jam_id, removed_track_id),
            )
            self._push_jam(jam_id)
        jam = self.find_by_id(jam_id)
        if jam is None:
            raise EntityNotFoundError(entity_name="Jam", entity_id=jam_id)
        return jam

    def add_participant(self, jam_id: int, user_id: int) -> bool:
        self._pull_deltas()
        now_str = datetime.now(UTC).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO jam_participants (jam_id, user_id, joined_at)
                VALUES (?, ?, ?)
                """,
                (jam_id, user_id, now_str),
            )
            added = cursor.rowcount > 0
            if added:
                self._push_jam(jam_id)
        return added

    def is_participant(self, jam_id: int, user_id: int) -> bool:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT 1 FROM jam_participants WHERE jam_id = ? AND user_id = ?",
            (jam_id, user_id),
        )
        if cursor.fetchone() is not None:
            return True
        jam = self.find_by_id(jam_id)
        return jam is not None and jam.host_user_id == user_id

    def list_participants(self, jam_id: int) -> list[int]:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT user_id FROM jam_participants WHERE jam_id = ? ORDER BY joined_at ASC",
            (jam_id,),
        )
        return [int(row["user_id"]) for row in cursor.fetchall()]

    def record_skip_vote(self, jam_id: int, track_id: int, user_id: int) -> bool:
        self._pull_deltas()
        now_str = datetime.now(UTC).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO jam_skip_votes (jam_id, track_id, user_id, voted_at)
                VALUES (?, ?, ?, ?)
                """,
                (jam_id, track_id, user_id, now_str),
            )
            recorded = cursor.rowcount > 0
            if recorded:
                self._push_jam(jam_id)
        return recorded

    def count_skip_votes(self, jam_id: int, track_id: int) -> int:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM jam_skip_votes WHERE jam_id = ? AND track_id = ?",
            (jam_id, track_id),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def clear_skip_votes(self, jam_id: int, track_id: int | None = None) -> None:
        self._pull_deltas()
        with transaction(self.conn) as cursor:
            if track_id is not None:
                cursor.execute(
                    "DELETE FROM jam_skip_votes WHERE jam_id = ? AND track_id = ?",
                    (jam_id, track_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM jam_skip_votes WHERE jam_id = ?",
                    (jam_id,),
                )
            changed = cursor.rowcount > 0
            if changed:
                self._push_jam(jam_id)


__all__ = ["SQLiteJamRepository"]
