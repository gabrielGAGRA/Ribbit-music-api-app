"""Use case for administrative blocking/soft-deleting of a track."""

import logging
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort


@dataclass(slots=True, frozen=True)
class BlockTrackUseCase:
    """Applies or removes soft-delete on a music track."""

    track_repo: TrackRepositoryPort
    catalog_file_port: TrackCatalogFilePort | None = None

    def execute(self, track_id: int, blocked: bool = True) -> bool:
        track = self.track_repo.find_by_id(track_id)
        if not track:
            raise EntityNotFoundError(f"Track {track_id} not found.")

        if blocked:
            track.mark_as_deleted()
        else:
            track.restore()

        self.track_repo.save(track)
        if self.catalog_file_port is not None:
            try:
                self.catalog_file_port.write_track_delta(
                    title=track.title,
                    artist=track.artist,
                    spotify_id=track.spotify_id,
                    is_deleted=track.is_deleted,
                )
            except ExternalServiceError as exc:
                logging.getLogger(__name__).warning(
                    "Failed to write track delta for track %s: %s", track_id, exc
                )
        return track.is_deleted


__all__ = ["BlockTrackUseCase"]
