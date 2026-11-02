"""Use case for filtering and searching track catalog."""

import contextlib
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
lazy from app.application.dtos.review_dtos import SearchTracksCommand
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import (
    CatalogTrack,
    TrackCatalogPort,
)
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class SearchTracksUseCase:
    """Searches music tracks by artist, album, genre, release year, or query text."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    music_service: TrackCatalogPort | None = None

    def execute(self, command: SearchTracksCommand) -> list[Track]:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        tracks = self.track_repo.find_by_filters(
            artist=command.artist,
            album=command.album,
            genre=command.genre,
            year=command.year,
            query=command.query,
            limit=command.limit,
            offset=command.offset,
        )

        query_term = (
            command.query
            or command.artist
            or command.album
            or command.genre
            or (str(command.year) if command.year is not None else None)
        )
        if not tracks and query_term and self.music_service is not None:
            catalog_tracks: list[CatalogTrack] = []
            with contextlib.suppress(ExternalServiceError):
                catalog_tracks = self.music_service.search_tracks(
                    query_term, limit=command.limit
                )
            for ct in catalog_tracks:
                candidate = Track(
                    title=ct.title or query_term,
                    artist=ct.artist or "Artista desconhecido",
                    album=ct.album,
                    duration_seconds=180,
                    genre="Desconhecido",
                    spotify_id=str(ct.external_id) if ct.external_id else None,
                    itunes_preview_url=ct.preview_url,
                )
                saved = self.track_repo.save(candidate)
                tracks.append(saved)

        if not user.is_adult:
            tracks = [t for t in tracks if not t.explicit]

        return tracks


__all__ = ["SearchTracksUseCase"]
