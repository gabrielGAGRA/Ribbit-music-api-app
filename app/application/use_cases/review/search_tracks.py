"""Use case for filtering and searching track catalog."""

import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
lazy from app.application.dtos.review_dtos import SearchTracksCommand
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort
lazy from app.application.ports.services.music_service import (
    CatalogTrack,
    TrackCatalogPort,
    TrackPreviewPort,
    lookup_matching_preview,
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
                preview = lookup_matching_preview(
                    self.track_preview_port, title=track.title, artist=track.artist
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
                extra={
                    "event": "catalog.delta_write.failed",
                    "status": "warning",
                    "track_id": saved.track_id,
                },
            )

    @staticmethod
    def _build_fallback_query(command: SearchTracksCommand) -> str | None:
        artist = (command.artist or "").strip()
        title = (command.query or "").strip()
        if artist and title:
            return f"artist:{artist} {title}"
        if artist:
            return f"artist:{artist}"
        return (
            command.query
            or command.album
            or command.genre
            or (str(command.year) if command.year is not None else None)
        )

    @staticmethod
    def _matches_search_filters(
        track: Track, artist_filter: str, title_filter: str
    ) -> bool:
        if artist_filter:
            return artist_filter in track.artist.lower() and (
                not title_filter or title_filter in track.title.lower()
            )
        if title_filter:
            return (
                title_filter in track.title.lower()
                or title_filter in track.artist.lower()
            )
        return True

    def _is_soft_deleted_catalog_track(self, ct: CatalogTrack) -> bool:
        existing = (
            self.track_repo.find_by_spotify_id(str(ct.external_id))
            if ct.external_id
            else None
        )
        if existing is None and ct.title and ct.artist:
            existing = self.track_repo.find_by_title_and_artist(ct.title, ct.artist)
        return existing is not None and existing.is_deleted is True

    def _fetch_spotify_fallback_tracks(
        self,
        command: SearchTracksCommand,
        user: object,
        query_term: str,
        artist_filter: str,
        title_filter: str,
    ) -> list[Track]:
        if self.music_service is None:
            return []
        catalog_tracks: list[CatalogTrack] = []
        with contextlib.suppress(ExternalServiceError, ValueError):
            catalog_tracks = self.music_service.search_tracks(
                query_term, limit=command.limit
            )
        added: list[Track] = []
        for ct in catalog_tracks:
            if self._is_soft_deleted_catalog_track(ct):
                continue
            candidate = self._build_track_from_catalog(ct, query_term)
            if not self._matches_search_filters(candidate, artist_filter, title_filter):
                continue
            if user.is_track_restricted_for_minor(candidate):  # type: ignore[attr-defined]
                continue
            saved = self.track_repo.save(candidate)
            if saved.is_deleted:
                continue
            self._write_new_track_delta(saved)
            added.append(saved)
        return added

    def execute(self, command: SearchTracksCommand) -> list[Track]:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        year_filter: int | list[int] | None = command.year
        if command.start_year is not None or command.end_year is not None:
            start_y = command.start_year if command.start_year is not None else 1970
            end_y = (
                command.end_year
                if command.end_year is not None
                else datetime.now(UTC).year
            )
            if start_y <= end_y:
                year_filter = list(range(start_y, end_y + 1))

        tracks = self.track_repo.find_by_filters(
            artist=command.artist,
            album=command.album,
            genre=command.genre,
            year=year_filter,
            query=command.query,
            min_rating=command.min_rating,
            sort_by=command.sort_by,
            include_deleted=command.include_deleted,
            block_explicit=user.is_minor(),
            excluded_genre_terms=user.restricted_genre_terms(),
            limit=command.limit,
            offset=command.offset,
        )

        artist_filter = (command.artist or "").strip().lower()
        title_filter = (command.query or "").strip().lower()
        query_term = self._build_fallback_query(command)
        has_rating_controls = (
            command.min_rating is not None or command.sort_by is not None
        )
        needs_fallback = not has_rating_controls and (
            not tracks
            or (
                bool(title_filter)
                and not any(
                    title_filter in t.title.lower()
                    or (not artist_filter and title_filter in t.artist.lower())
                    for t in tracks
                )
            )
        )
        if (
            needs_fallback
            and query_term
            and self.music_service is not None
            and user.is_adult
        ):
            tracks.extend(
                self._fetch_spotify_fallback_tracks(
                    command, user, query_term, artist_filter, title_filter
                )
            )

        results = [
            track
            for track in tracks
            if not user.is_track_restricted_for_minor(track)
            and self._matches_search_filters(track, artist_filter, title_filter)
        ]
        if title_filter and command.sort_by is None:
            results.sort(
                key=lambda t: (
                    0
                    if t.title.lower() == title_filter
                    or t.artist.lower() == title_filter
                    else 1
                    if title_filter in t.title.lower()
                    or title_filter in t.artist.lower()
                    else 2
                )
            )
        return results


__all__ = ["SearchTracksUseCase"]
