"""Use case for updating a track's genre and writing back delta to catalog storage."""

import logging
from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ExternalServiceError,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort


@dataclass(slots=True, frozen=True)
class UpdateTrackGenreUseCase:
    """Updates the genre classification on a track and writes a delta to catalog storage."""

    track_repo: TrackRepositoryPort
    catalog_file_port: TrackCatalogFilePort | None = None

    def execute(self, track_id: int, genre: str) -> str:
        track = self.track_repo.find_by_id(track_id)
        if not track:
            raise EntityNotFoundError(f"Track {track_id} not found.")

        try:
            track.set_genre(genre)
        except ValueError as exc:
            raise BusinessRuleViolationError(str(exc)) from exc

        self.track_repo.save(track)
        if self.catalog_file_port is not None:
            try:
                self.catalog_file_port.write_track_delta(
                    title=track.title,
                    artist=track.artist,
                    preview_url=track.itunes_preview_url,
                    genre=track.genre,
                    spotify_id=track.spotify_id,
                )
            except ExternalServiceError as exc:
                logging.getLogger(__name__).warning(
                    "Failed to write track delta for track %s: %s", track_id, exc
                )
        return track.genre


__all__ = ["UpdateTrackGenreUseCase"]
