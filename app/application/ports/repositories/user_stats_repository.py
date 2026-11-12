"""Read-only analytical query port for user listening statistics."""

from typing import Protocol, runtime_checkable

lazy from app.application.dtos.user_dtos import AnnualStatsResult


@runtime_checkable
class UserStatsRepositoryPort(Protocol):
    """Aggregates user interaction, track, review, playlist, and jam statistics."""

    def get_user_stats(
        self, user_id: int, year: int | None = None
    ) -> AnnualStatsResult: ...
