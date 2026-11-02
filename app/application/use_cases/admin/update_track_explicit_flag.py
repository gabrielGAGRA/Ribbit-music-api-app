"""Use case for toggling the explicit content flag on a track."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort


@dataclass(slots=True, frozen=True)
class UpdateTrackExplicitFlagUseCase:
    """Updates whether a music track is marked as explicit for minors."""

    track_repo: TrackRepositoryPort

    def execute(self, track_id: int, explicit: bool) -> bool:
        track = self.track_repo.find_by_id(track_id)
        if not track:
            raise EntityNotFoundError(f"Track {track_id} not found.")

        track.set_explicit(explicit)
        self.track_repo.save(track)
        return track.explicit
