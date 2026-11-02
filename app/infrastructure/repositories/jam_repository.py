"""SQLite implementation of the Jam session and queue persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.jam import Jam, JamQueueItem


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
    deck_source = row["deck_source"] if "deck_source" in keys else "livre"
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

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_id(self, jam_id: int) -> Jam | None:
        cursor = self.conn.execute(
            "SELECT * FROM jams WHERE jam_id = ?",
            (jam_id,),
        )
        row = cursor.fetchone()
        return _row_to_jam(row) if row else None

    def find_by_code(self, room_code: str) -> Jam | None:
        cursor = self.conn.execute(
            "SELECT * FROM jams WHERE room_code = ? AND is_active = 1",
            (room_code,),
        )
        row = cursor.fetchone()
        return _row_to_jam(row) if row else None

    def save(self, jam: Jam) -> Jam:
        if jam.jam_id is not None:
            cursor = self.conn.execute(
                "SELECT jam_id FROM jams WHERE jam_id = ?",
                (jam.jam_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
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
                self.conn.commit()
                return self.find_by_id(jam.jam_id) or jam
            raise EntityNotFoundError(entity_name="Jam", entity_id=jam.jam_id)

        created_at_str = (jam.created_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
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
        self.conn.commit()
        new_id = cursor.lastrowid
        if new_id is not None:
            return self.find_by_id(new_id) or jam
        return jam

    def find_queue_item(self, jam_id: int, track_id: int) -> JamQueueItem | None:
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
        cursor = self.conn.execute(
            """
            SELECT jam_queue_id FROM jam_queue_items
            WHERE jam_id = ? AND track_id = ?
            """,
            (item.jam_id, item.track_id),
        )
        existing = cursor.fetchone()
        if existing:
            self.conn.execute(
                """
                UPDATE jam_queue_items
                SET vote_points = ?
                WHERE jam_id = ? AND track_id = ?
                """,
                (item.vote_points, item.jam_id, item.track_id),
            )
            self.conn.commit()
            return self.find_queue_item(item.jam_id, item.track_id) or item

        added_at_str = (item.added_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO jam_queue_items (jam_id, track_id, vote_points, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (item.jam_id, item.track_id, item.vote_points, added_at_str),
        )
        self.conn.commit()
        return self.find_queue_item(item.jam_id, item.track_id) or item

    def list_queue(self, jam_id: int) -> list[JamQueueItem]:
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
        cursor = self.conn.execute(
            """
            DELETE FROM jam_queue_items
            WHERE jam_id = ? AND track_id = ?
            """,
            (jam_id, track_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def advance_playback(
        self, jam_id: int, new_track_id: int, removed_track_id: int
    ) -> Jam:
        cursor = self.conn.execute(
            "SELECT jam_id FROM jams WHERE jam_id = ?",
            (jam_id,),
        )
        if not cursor.fetchone():
            raise EntityNotFoundError(entity_name="Jam", entity_id=jam_id)

        self.conn.execute(
            """
            UPDATE jams
            SET current_track_id = ?
            WHERE jam_id = ?
            """,
            (new_track_id, jam_id),
        )
        self.conn.execute(
            """
            DELETE FROM jam_queue_items
            WHERE jam_id = ? AND track_id = ?
            """,
            (jam_id, removed_track_id),
        )
        self.conn.commit()
        jam = self.find_by_id(jam_id)
        if jam is None:
            raise EntityNotFoundError(entity_name="Jam", entity_id=jam_id)
        return jam

    def add_participant(self, jam_id: int, user_id: int) -> bool:
        now_str = datetime.now(UTC).isoformat()
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO jam_participants (jam_id, user_id, joined_at)
            VALUES (?, ?, ?)
            """,
            (jam_id, user_id, now_str),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def is_participant(self, jam_id: int, user_id: int) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM jam_participants WHERE jam_id = ? AND user_id = ?",
            (jam_id, user_id),
        )
        if cursor.fetchone() is not None:
            return True
        jam = self.find_by_id(jam_id)
        return jam is not None and jam.host_user_id == user_id

    def list_participants(self, jam_id: int) -> list[int]:
        cursor = self.conn.execute(
            "SELECT user_id FROM jam_participants WHERE jam_id = ? ORDER BY joined_at ASC",
            (jam_id,),
        )
        return [int(row["user_id"]) for row in cursor.fetchall()]

    def record_skip_vote(self, jam_id: int, track_id: int, user_id: int) -> bool:
        now_str = datetime.now(UTC).isoformat()
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO jam_skip_votes (jam_id, track_id, user_id, voted_at)
            VALUES (?, ?, ?, ?)
            """,
            (jam_id, track_id, user_id, now_str),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def count_skip_votes(self, jam_id: int, track_id: int) -> int:
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM jam_skip_votes WHERE jam_id = ? AND track_id = ?",
            (jam_id, track_id),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def clear_skip_votes(self, jam_id: int, track_id: int | None = None) -> None:
        if track_id is not None:
            self.conn.execute(
                "DELETE FROM jam_skip_votes WHERE jam_id = ? AND track_id = ?",
                (jam_id, track_id),
            )
        else:
            self.conn.execute(
                "DELETE FROM jam_skip_votes WHERE jam_id = ?",
                (jam_id,),
            )
        self.conn.commit()


__all__ = ["SQLiteJamRepository"]
