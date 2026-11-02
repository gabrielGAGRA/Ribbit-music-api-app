"""Use case for updating a track's genre and writing back delta to catalog storage."""

import contextlib
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
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

        track.genre = genre.strip()
        self.track_repo.save(track)
        if self.catalog_file_port is not None:
            with contextlib.suppress(Exception):
                self.catalog_file_port.write_track_delta(
                    title=track.title,
                    artist=track.artist,
                    preview_url=track.itunes_preview_url,
                    genre=track.genre,
                    spotify_id=track.spotify_id,
                )
        return track.genre


__all__ = ["UpdateTrackGenreUseCase"]
