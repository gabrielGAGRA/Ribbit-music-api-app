"""Use case for fetching the next track candidate for swipe discovery."""

import logging
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
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

    def execute(self, user_id: int) -> Track | None:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        is_minor = user.is_minor()
        blocked_genres = tuple(user.blocked_genres)
        interacted_ids = self.interaction_repo.list_interacted_track_ids(user_id)

        candidates = self.track_repo.list_active(
            excluded_genres=blocked_genres,
            excluded_genre_terms=(
                tuple(sorted(user.MINOR_RESTRICTED_GENRE_TERMS)) if is_minor else ()
            ),
            block_explicit=is_minor,
            excluded_ids=interacted_ids,
            limit=1,
        )

        if not candidates:
            return None

        track = candidates[0]
        needs_preview = not track.itunes_preview_url
        needs_genre = not track.has_known_genre()
        if (needs_preview or needs_genre) and self.track_preview_port is not None:
            preview = self.track_preview_port.find_preview(
                f"{track.artist} {track.title}"
            )
            if preview:
                changed = track.merge_missing_metadata(
                    itunes_preview_url=str(preview.preview_url)
                    if needs_preview and preview.preview_url
                    else None,
                    genre=str(preview.genre) if needs_genre and preview.genre else None,
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
                                spotify_id=track.spotify_id,
                            )
                        except ExternalServiceError as exc:
                            logging.getLogger(__name__).warning(
                                "Failed to write track delta for track %s: %s",
                                track.track_id,
                                exc,
                            )

        return track


__all__ = ["GetNextDiscoveryTrackUseCase"]
