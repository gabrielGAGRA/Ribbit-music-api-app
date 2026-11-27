"""Use case for searching external music providers to add tracks to the Delta Table."""

import contextlib
from dataclasses import dataclass

from app.domain.exceptions import ExternalServiceError
lazy from app.application.dtos.admin_dtos import ExternalTrackCandidateResult
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.music_service import (
    CatalogTrack,
    TrackCatalogPort,
    TrackPreviewPort,
    lookup_matching_preview,
)


def _build_queries(title: str | None, artist: str | None) -> tuple[str, str]:
    clean_title = (title or "").strip()
    clean_artist = (artist or "").strip()
    if clean_title and clean_artist:
        return (
            f"track:{clean_title} artist:{clean_artist}",
            f"{clean_artist} {clean_title}",
        )
    if clean_title:
        return clean_title, clean_title
    return f"artist:{clean_artist}", clean_artist


@dataclass(slots=True, frozen=True)
class SearchExternalTracksUseCase:
    """Searches Spotify/iTunes by title and artist and flags tracks already in catalog."""

    track_repo: TrackRepositoryPort
    music_service: TrackCatalogPort | None = None
    track_preview_port: TrackPreviewPort | None = None

    def _is_in_catalog(
        self, *, title: str, artist: str, spotify_id: str | None
    ) -> bool:
        if spotify_id and self.track_repo.find_by_spotify_id(spotify_id) is not None:
            return True
        return self.track_repo.find_by_title_and_artist(title, artist) is not None

    def _from_catalog_track(
        self, ct: CatalogTrack, fallback_title: str
    ) -> ExternalTrackCandidateResult:
        title = (ct.title or fallback_title).strip() or "Unknown Title"
        artist = ct.artist.strip() or "Unknown Artist"
        spotify_id = str(ct.external_id) if ct.external_id else None
        duration_seconds = max(1, ct.duration_ms // 1000) if ct.duration_ms else 180
        genre = "Unknown"
        cover_url = ct.cover_url
        preview_url = ct.preview_url
        country: str | None = None
        album = ct.album
        release_year = ct.release_year

        if self.track_preview_port is not None and (
            not preview_url or not cover_url or genre == "Unknown"
        ):
            preview = None
            with contextlib.suppress(ExternalServiceError):
                preview = lookup_matching_preview(
                    self.track_preview_port, title=title, artist=artist
                )
            if preview is not None:
                preview_url = preview_url or (preview.preview_url or None)
                cover_url = cover_url or (preview.cover_url or None)
                genre = preview.genre or genre
                country = preview.country or country
                album = album or preview.album
                release_year = release_year or preview.release_year

        return ExternalTrackCandidateResult(
            title=title,
            artist=artist,
            duration_seconds=duration_seconds,
            genre=genre,
            spotify_id=spotify_id,
            album=album,
            country=country,
            release_year=release_year,
            cover_url=cover_url,
            itunes_preview_url=preview_url,
            explicit=ct.explicit,
            already_in_catalog=self._is_in_catalog(
                title=title, artist=artist, spotify_id=spotify_id
            ),
        )

    def execute(
        self,
        *,
        title: str | None = None,
        artist: str | None = None,
        limit: int = 10,
    ) -> list[ExternalTrackCandidateResult]:
        if not (title or "").strip() and not (artist or "").strip():
            return []

        spotify_query, fallback_term = _build_queries(title, artist)
        catalog_tracks: list[CatalogTrack] = []
        if self.music_service is not None:
            with contextlib.suppress(ExternalServiceError):
                catalog_tracks = self.music_service.search_tracks(
                    spotify_query, limit=limit
                )

        if catalog_tracks:
            fallback_title = (title or "").strip() or "Unknown Title"
            return [
                self._from_catalog_track(ct, fallback_title) for ct in catalog_tracks
            ]

        if self.track_preview_port is not None:
            preview = None
            with contextlib.suppress(ExternalServiceError):
                preview = self.track_preview_port.find_preview(fallback_term)
            if preview is not None:
                p_title = (preview.title or (title or "")).strip() or "Unknown Title"
                p_artist = (
                    preview.artist or (artist or "")
                ).strip() or "Unknown Artist"
                return [
                    ExternalTrackCandidateResult(
                        title=p_title,
                        artist=p_artist,
                        duration_seconds=180,
                        genre=preview.genre or "Unknown",
                        album=preview.album,
                        country=preview.country,
                        release_year=preview.release_year,
                        cover_url=preview.cover_url or None,
                        itunes_preview_url=preview.preview_url or None,
                        already_in_catalog=self._is_in_catalog(
                            title=p_title, artist=p_artist, spotify_id=None
                        ),
                    )
                ]

        return []


__all__ = ["SearchExternalTracksUseCase"]
