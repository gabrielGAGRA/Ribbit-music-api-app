"""Use case for fetching the next track candidate for swipe discovery."""

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
lazy from app.application.ports.services.music_service import (
    TrackPreviewPort,
    lookup_matching_preview,
)
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


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
    max_preview_attempts: int = 5
    rng: random.Random | None = None

    def _list_candidates(
        self,
        user: User,
        blocked_genres: tuple[str, ...],
        interacted_ids: list[int],
    ) -> list[Track]:
        if user.favorite_genres:
            return self.track_repo.list_active(
                excluded_genres=blocked_genres,
                excluded_genre_terms=user.restricted_genre_terms(),
                preferred_genres=tuple(user.favorite_genres),
                block_explicit=user.is_minor(),
                excluded_ids=interacted_ids,
                limit=self.candidate_pool_size,
            )
        return self.track_repo.list_active(
            excluded_genres=blocked_genres,
            excluded_genre_terms=user.restricted_genre_terms(),
            block_explicit=user.is_minor(),
            excluded_ids=interacted_ids,
            limit=self.candidate_pool_size,
        )

    def _write_track_delta(self, track: Track) -> None:
        if self.catalog_file_port is None:
            return
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
                created_at=track.created_at.isoformat() if track.created_at else None,
            )
        except ExternalServiceError as exc:
            logging.getLogger(__name__).warning(
                "Failed to write track delta for track %s: %s",
                track.track_id,
                exc,
            )

    def execute(self, user_id: int) -> Track | None:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        candidates = self._list_candidates(
            user,
            tuple(user.blocked_genres),
            self.interaction_repo.list_interacted_track_ids(user_id),
        )
        preview_port = self.track_preview_port
        remaining = list(candidates)

        for _ in range(max(1, self.max_preview_attempts)):
            track = select_weighted_track(remaining, user, rng=self.rng)
            if track is None:
                return None
            if preview_port is None:
                return track

            needs_preview = _is_missing_or_placeholder_url(track.itunes_preview_url)
            needs_genre = not track.has_known_genre()
            needs_cover = _is_missing_or_placeholder_url(track.cover_url)
            external_error = False
            if needs_preview or needs_genre or needs_cover:
                external_error = self._enrich_track_from_preview(
                    track,
                    preview_port=preview_port,
                    needs_preview=needs_preview,
                    needs_genre=needs_genre,
                    needs_cover=needs_cover,
                )
            if external_error or not _is_missing_or_placeholder_url(
                track.itunes_preview_url
            ):
                return track

            track.mark_as_deleted()
            self.track_repo.save(track)
            self._write_track_delta(track)
            remaining = [t for t in remaining if t is not track]

        return None

    def _enrich_track_from_preview(
        self,
        track: Track,
        *,
        preview_port: TrackPreviewPort,
        needs_preview: bool,
        needs_genre: bool,
        needs_cover: bool,
    ) -> bool:
        try:
            preview = lookup_matching_preview(
                preview_port, title=track.title, artist=track.artist
            )
        except ExternalServiceError:
            return True
        if not preview:
            return False
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
            self._write_track_delta(track)
        return False


__all__ = ["GetNextDiscoveryTrackUseCase"]
