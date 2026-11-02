"""SQLite implementation of the interaction persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.domain.models.interaction import Interaction, InteractionAction


def _row_to_interaction(row: sqlite3.Row) -> Interaction:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    return Interaction(
        interaction_id=row["interaction_id"],
        user_id=row["user_id"],
        track_id=row["track_id"],
        action=InteractionAction(row["action"]),
        created_at=created_at,
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
            INSERT INTO interactions (user_id, track_id, action, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, track_id) DO UPDATE SET action = excluded.action
            """,
            (
                interaction.user_id,
                interaction.track_id,
                interaction.action.value,
                created_at_str,
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
                ORDER BY created_at DESC
                """,
                (user_id, action.value),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM interactions
                WHERE user_id = ?
                ORDER BY created_at DESC
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


__all__ = ["SQLiteInteractionRepository"]
