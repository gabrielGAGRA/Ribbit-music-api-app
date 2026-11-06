"""Use case for fetching the next track candidate for swipe discovery."""

import contextlib
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
        needs_preview = not track.itunes_preview_url
        needs_genre = not track.genre
        needs_cover = not track.cover_url
        if (
            needs_preview or needs_genre or needs_cover
        ) and self.track_preview_port is not None:
            preview = None
            with contextlib.suppress(ExternalServiceError):
                preview = self.track_preview_port.find_preview(
                    f"{track.artist} {track.title}"
                )
            if preview:
                changed = False
                if needs_preview and preview.preview_url:
                    track.itunes_preview_url = str(preview.preview_url)
                    changed = True
                if needs_genre and preview.genre:
                    track.genre = str(preview.genre)
                    changed = True
                if needs_cover and preview.cover_url:
                    track.cover_url = str(preview.cover_url)
                    changed = True
                if changed:
                    self.track_repo.save(track)
                    if self.catalog_file_port is not None:
                        with contextlib.suppress(Exception):
                            self.catalog_file_port.write_track_delta(
                                title=track.title,
                                artist=track.artist,
                                preview_url=track.itunes_preview_url,
                                genre=track.genre,
                                cover_url=track.cover_url,
                                spotify_id=track.spotify_id,
                            )

        return track


__all__ = ["GetNextDiscoveryTrackUseCase"]
