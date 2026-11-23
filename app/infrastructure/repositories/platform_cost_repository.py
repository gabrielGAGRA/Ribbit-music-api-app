"""SQLite implementation of the platform cost settings repository port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.platform_cost_repository import (
    PlatformCostRepositoryPort,
)
from app.domain.models.platform_costs import PlatformCostSettings
from app.infrastructure.repositories.connection import transaction


class SQLitePlatformCostRepository(PlatformCostRepositoryPort):
    """SQLite adapter implementing PlatformCostRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_settings(self) -> PlatformCostSettings:
        row = self.conn.execute(
            """
            SELECT
                content_cost_per_track,
                infrastructure_fixed_cost,
                infrastructure_cost_per_user,
                updated_at
            FROM platform_cost_settings
            WHERE settings_id = 1
            """
        ).fetchone()
        if not row:
            return PlatformCostSettings()
        return PlatformCostSettings(
            content_cost_per_track=float(row["content_cost_per_track"]),
            infrastructure_fixed_cost=float(row["infrastructure_fixed_cost"]),
            infrastructure_cost_per_user=float(row["infrastructure_cost_per_user"]),
            updated_at=datetime.fromisoformat(str(row["updated_at"]))
            if row["updated_at"]
            else None,
        )

    def save_settings(self, settings: PlatformCostSettings) -> PlatformCostSettings:
        updated_at = settings.updated_at or datetime.now(UTC)
        updated_at_str = updated_at.isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO platform_cost_settings (
                    settings_id,
                    content_cost_per_track,
                    infrastructure_fixed_cost,
                    infrastructure_cost_per_user,
                    updated_at
                ) VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(settings_id) DO UPDATE SET
                    content_cost_per_track = excluded.content_cost_per_track,
                    infrastructure_fixed_cost = excluded.infrastructure_fixed_cost,
                    infrastructure_cost_per_user = excluded.infrastructure_cost_per_user,
                    updated_at = excluded.updated_at
                """,
                (
                    settings.content_cost_per_track,
                    settings.infrastructure_fixed_cost,
                    settings.infrastructure_cost_per_user,
                    updated_at_str,
                ),
            )
        return PlatformCostSettings(
            content_cost_per_track=settings.content_cost_per_track,
            infrastructure_fixed_cost=settings.infrastructure_fixed_cost,
            infrastructure_cost_per_user=settings.infrastructure_cost_per_user,
            updated_at=updated_at,
        )


PlatformCostRepository = SQLitePlatformCostRepository
