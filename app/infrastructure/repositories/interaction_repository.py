"""SQLite implementation of the interaction persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.domain.models.interaction import Interaction, InteractionAction
from app.infrastructure.repositories.connection import transaction


def _row_to_interaction(row: sqlite3.Row) -> Interaction:
    keys = row.keys()
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    return Interaction(
        interaction_id=row["interaction_id"],
        user_id=row["user_id"],
        track_id=row["track_id"],
        action=InteractionAction(row["action"]),
        created_at=created_at,
        source=row["source"] if "source" in keys else None,
        jam_id=row["jam_id"] if "jam_id" in keys else None,
    )


class SQLiteInteractionRepository(InteractionRepositoryPort):
    """SQLite adapter implementing InteractionRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_user_and_track(self, user_id: int, track_id: int) -> Interaction | None:
        cursor = self.conn.execute(
            """
            SELECT * FROM interactions
            WHERE user_id = ? AND track_id = ?
            """,
            (user_id, track_id),
        )
        row = cursor.fetchone()
        return _row_to_interaction(row) if row else None

    def save(self, interaction: Interaction) -> Interaction:
        created_at_str = (interaction.created_at or datetime.now(UTC)).isoformat()
        self.conn.execute(
            """
            INSERT INTO interactions (
                user_id, track_id, action, created_at, source, jam_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, track_id) DO UPDATE SET
                action = excluded.action,
                created_at = excluded.created_at,
                source = excluded.source,
                jam_id = excluded.jam_id
            """,
            (
                interaction.user_id,
                interaction.track_id,
                interaction.action.value,
                created_at_str,
                interaction.source,
                interaction.jam_id,
            ),
        )
        self.conn.commit()
        return (
            self.find_by_user_and_track(interaction.user_id, interaction.track_id)
            or interaction
        )

    def list_by_user(
        self, user_id: int, action: InteractionAction | None = None
    ) -> list[Interaction]:
        if action is not None:
            cursor = self.conn.execute(
                """
                SELECT * FROM interactions
                WHERE user_id = ? AND action = ?
                ORDER BY created_at DESC, interaction_id DESC
                """,
                (user_id, action.value),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM interactions
                WHERE user_id = ?
                ORDER BY created_at DESC, interaction_id DESC
                """,
                (user_id,),
            )
        rows = cursor.fetchall()
        return [_row_to_interaction(r) for r in rows]

    def list_interacted_track_ids(self, user_id: int) -> list[int]:
        cursor = self.conn.execute(
            "SELECT track_id FROM interactions WHERE user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        return [int(r["track_id"]) for r in rows]

    def delete_latest_discovery(self, user_id: int) -> Interaction | None:
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                SELECT * FROM interactions
                WHERE user_id = ? AND source = 'discovery'
                ORDER BY created_at DESC, interaction_id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            interaction = _row_to_interaction(row)
            cursor.execute(
                "DELETE FROM interactions WHERE interaction_id = ?",
                (interaction.interaction_id,),
            )
        return interaction


__all__ = ["SQLiteInteractionRepository"]
