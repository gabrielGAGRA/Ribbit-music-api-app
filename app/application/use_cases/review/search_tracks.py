"""Use case for filtering and searching track catalog."""

import contextlib
import logging
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
lazy from app.application.dtos.review_dtos import SearchTracksCommand
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort
lazy from app.application.ports.services.music_service import (
    CatalogTrack,
    TrackCatalogPort,
    TrackPreviewPort,
)
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class SearchTracksUseCase:
    """Searches music tracks by artist, album, genre, release year, or query text."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    music_service: TrackCatalogPort | None = None
    track_preview_port: TrackPreviewPort | None = None
    catalog_file_port: TrackCatalogFilePort | None = None

    def _build_track_from_catalog(self, ct: CatalogTrack, query_term: str) -> Track:
        title = ct.title or query_term
        artist = ct.artist or "Unknown Artist"
        duration_seconds = max(1, ct.duration_ms // 1000) if ct.duration_ms else 180
        track = Track(
            title=title,
            artist=artist,
            album=ct.album,
            duration_seconds=duration_seconds,
            genre="Unknown",
            release_year=ct.release_year,
            cover_url=ct.cover_url,
            spotify_id=str(ct.external_id) if ct.external_id else None,
            itunes_preview_url=ct.preview_url,
            explicit=ct.explicit,
        )
        if self.track_preview_port is not None and (
            not track.itunes_preview_url
            or not track.has_known_genre()
            or not track.cover_url
            or not track.country
            or not track.album
            or track.release_year is None
        ):
            preview = None
            with contextlib.suppress(ExternalServiceError):
                preview = self.track_preview_port.find_preview(
                    f"{track.artist} {track.title}"
                )
            if preview is not None:
                track.merge_missing_metadata(
                    itunes_preview_url=str(preview.preview_url)
                    if not track.itunes_preview_url and preview.preview_url
                    else None,
                    genre=str(preview.genre)
                    if not track.has_known_genre() and preview.genre
                    else None,
                    cover_url=str(preview.cover_url)
                    if not track.cover_url and preview.cover_url
                    else None,
                )
                if not track.country and preview.country:
                    track.country = preview.country
                if not track.album and preview.album:
                    track.album = preview.album
                if track.release_year is None and preview.release_year is not None:
                    track.release_year = preview.release_year
        return track

    def _write_new_track_delta(self, saved: Track) -> None:
        if self.catalog_file_port is None:
            return
        try:
            self.catalog_file_port.write_track_delta(
                title=saved.title,
                artist=saved.artist,
                preview_url=saved.itunes_preview_url,
                genre=saved.genre,
                cover_url=saved.cover_url,
                spotify_id=saved.spotify_id,
                album=saved.album,
                duration_seconds=saved.duration_seconds,
                country=saved.country,
                release_year=saved.release_year,
                explicit=saved.explicit,
                is_deleted=saved.is_deleted,
                created_at=saved.created_at.isoformat() if saved.created_at else None,
            )
        except ExternalServiceError as exc:
            logging.getLogger(__name__).warning(
                "Failed to write track delta for track %s: %s",
                saved.track_id,
                exc,
            )

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
        if (
            not tracks
            and query_term
            and self.music_service is not None
            and user.is_adult
        ):
            catalog_tracks: list[CatalogTrack] = []
            with contextlib.suppress(ExternalServiceError, ValueError):
                catalog_tracks = self.music_service.search_tracks(
                    query_term, limit=command.limit
                )
            for ct in catalog_tracks:
                candidate = self._build_track_from_catalog(ct, query_term)
                saved = self.track_repo.save(candidate)
                self._write_new_track_delta(saved)
                tracks.append(saved)

        return [
            track for track in tracks if not user.is_track_restricted_for_minor(track)
        ]


__all__ = ["SearchTracksUseCase"]
