"""Use case for listing blocked/soft-deleted tracks."""

from dataclasses import dataclass

lazy from app.application.dtos.admin_dtos import AdminCatalogTrackResult
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class ListBlockedTracksUseCase:
    """Returns all catalog tracks marked as blocked (is_deleted = 1)."""

    track_repo: TrackRepositoryPort

    def execute(self) -> list[Track]:
        return self.track_repo.list_blocked()

    def execute_with_metrics(self) -> list[AdminCatalogTrackResult]:
        return self.track_repo.list_blocked_with_metrics()


__all__ = ["ListBlockedTracksUseCase"]
