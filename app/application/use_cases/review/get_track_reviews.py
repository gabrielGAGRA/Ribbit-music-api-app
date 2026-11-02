"""Use case for listing all active reviews of a track."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class GetTrackReviewsUseCase:
    """Retrieves all non-deleted reviews for a given music track."""

    track_repo: TrackRepositoryPort
    review_repo: ReviewRepositoryPort

    def execute(self, track_id: int, limit: int = 50) -> list[ReviewComment]:
        track = self.track_repo.find_by_id(track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError("Track not found or inactive.")

        return self.review_repo.list_by_track(track_id, limit=limit)
