"""Use case for fetching the next track candidate for swipe discovery."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import TrackPreviewPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class GetNextDiscoveryTrackUseCase:
    """Finds the next active track matching user age and genre preferences."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_preview_port: TrackPreviewPort | None = None

    def execute(self, user_id: int) -> Track | None:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        block_explicit = user.is_minor()
        blocked_genres = tuple(user.blocked_genres)
        interacted_ids = self.interaction_repo.list_interacted_track_ids(user_id)

        candidates = self.track_repo.list_active(
            excluded_genres=blocked_genres,
            block_explicit=block_explicit,
            excluded_ids=interacted_ids,
            limit=1,
        )

        if not candidates:
            return None

        track = candidates[0]
        if not track.itunes_preview_url and self.track_preview_port is not None:
            preview = self.track_preview_port.find_preview(
                f"{track.artist} {track.title}"
            )
            if preview and preview.preview_url:
                track.itunes_preview_url = str(preview.preview_url)
                self.track_repo.save(track)

        return track
