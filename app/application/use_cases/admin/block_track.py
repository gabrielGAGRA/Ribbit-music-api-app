"""Use case for administrative blocking/soft-deleting of a track."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort


@dataclass(slots=True, frozen=True)
class BlockTrackUseCase:
    """Applies or removes soft-delete on a music track."""

    track_repo: TrackRepositoryPort

    def execute(self, track_id: int, blocked: bool = True) -> bool:
        track = self.track_repo.find_by_id(track_id)
        if not track:
            raise EntityNotFoundError(f"Track {track_id} not found.")

        if blocked:
            track.mark_as_deleted()
        else:
            track.restore()

        self.track_repo.save(track)
        return track.is_deleted


__all__ = ["BlockTrackUseCase"]
