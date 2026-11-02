"""Use case for listing blocked/soft-deleted tracks."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class ListBlockedTracksUseCase:
    """Returns all catalog tracks marked as blocked (is_deleted = 1)."""

    track_repo: TrackRepositoryPort

    def execute(self) -> list[Track]:
        return self.track_repo.list_blocked()


__all__ = ["ListBlockedTracksUseCase"]
