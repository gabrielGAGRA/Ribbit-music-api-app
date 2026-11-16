"""Use case for fetching the next track candidate for swipe discovery."""

import contextlib
import logging
from dataclasses import dataclass
lazy import random

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
from app.domain.services.recommendation import select_weighted_track
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort
lazy from app.application.ports.services.music_service import TrackPreviewPort
lazy from app.domain.models.track import Track


def _is_missing_or_placeholder_url(url: str | None) -> bool:
    return not url or "example.com" in url


@dataclass(slots=True, frozen=True)
class GetNextDiscoveryTrackUseCase:
    """Finds the next active track matching user age and genre preferences."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_preview_port: TrackPreviewPort | None = None
    catalog_file_port: TrackCatalogFilePort | None = None
    candidate_pool_size: int = 100
    rng: random.Random | None = None

    def execute(self, user_id: int) -> Track | None:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        blocked_genres = tuple(user.blocked_genres)
        interacted_ids = self.interaction_repo.list_interacted_track_ids(user_id)

        candidates = self.track_repo.list_active(
            excluded_genres=blocked_genres,
            excluded_genre_terms=user.restricted_genre_terms(),
            block_explicit=user.is_minor(),
            excluded_ids=interacted_ids,
            limit=self.candidate_pool_size,
        )

        track = select_weighted_track(candidates, user, rng=self.rng)
        if track is None:
            return None
        needs_preview = _is_missing_or_placeholder_url(track.itunes_preview_url)
        needs_genre = not track.has_known_genre()
        needs_cover = _is_missing_or_placeholder_url(track.cover_url)
        preview_port = self.track_preview_port
        if (needs_preview or needs_genre or needs_cover) and preview_port is not None:
            self._enrich_track_from_preview(
                track,
                preview_port=preview_port,
                needs_preview=needs_preview,
                needs_genre=needs_genre,
                needs_cover=needs_cover,
            )

        return track

    def _enrich_track_from_preview(
        self,
        track: Track,
        *,
        preview_port: TrackPreviewPort,
        needs_preview: bool,
        needs_genre: bool,
        needs_cover: bool,
    ) -> None:
        preview = None
        with contextlib.suppress(ExternalServiceError):
            preview = preview_port.find_preview(f"{track.artist} {track.title}")
        if not preview:
            return
        if (
            needs_preview
            and preview.preview_url
            and _is_missing_or_placeholder_url(track.itunes_preview_url)
        ):
            track.itunes_preview_url = None
        if (
            needs_cover
            and preview.cover_url
            and _is_missing_or_placeholder_url(track.cover_url)
        ):
            track.cover_url = None
        changed = track.merge_missing_metadata(
            itunes_preview_url=str(preview.preview_url)
            if needs_preview and preview.preview_url
            else None,
            genre=str(preview.genre) if needs_genre and preview.genre else None,
            cover_url=str(preview.cover_url)
            if needs_cover and preview.cover_url
            else None,
        )
        if changed:
            self.track_repo.save(track)
            if self.catalog_file_port is not None:
                try:
                    self.catalog_file_port.write_track_delta(
                        title=track.title,
                        artist=track.artist,
                        preview_url=track.itunes_preview_url,
                        genre=track.genre,
                        cover_url=track.cover_url,
                        spotify_id=track.spotify_id,
                        album=track.album,
                        duration_seconds=track.duration_seconds,
                        country=track.country,
                        release_year=track.release_year,
                        explicit=track.explicit,
                        is_deleted=track.is_deleted,
                        created_at=track.created_at.isoformat()
                        if track.created_at
                        else None,
                    )
                except ExternalServiceError as exc:
                    logging.getLogger(__name__).warning(
                        "Failed to write track delta for track %s: %s",
                        track.track_id,
                        exc,
                    )


__all__ = ["GetNextDiscoveryTrackUseCase"]
