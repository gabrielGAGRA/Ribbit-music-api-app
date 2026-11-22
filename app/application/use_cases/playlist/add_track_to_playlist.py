"""Use case for adding an individual track to a playlist."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.interaction import (
    Interaction,
    InteractionAction,
    InteractionSource,
)
from app.domain.models.track_access import TrackAccess
lazy from app.application.dtos.playlist_dtos import AddTrackToPlaylistCommand
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.playlist import Playlist


@dataclass(slots=True, frozen=True)
class AddTrackToPlaylistUseCase:
    """Adds a track to an aggregate playlist after validating ownership and constraints."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    interaction_repo: InteractionRepositoryPort | None = None
    track_access_repo: TrackAccessRepositoryPort | None = None

    def _record_access(self, user_id: int, track_id: int) -> None:
        if self.track_access_repo is not None:
            self.track_access_repo.record(
                TrackAccess(user_id=user_id, track_id=track_id, source="playlist")
            )

    def execute(self, command: AddTrackToPlaylistCommand) -> Playlist:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        playlist = self.playlist_repo.find_by_id(command.playlist_id)
        if not playlist:
            raise EntityNotFoundError(
                f"Playlist with ID {command.playlist_id} not found."
            )

        if not playlist.is_owned_by(command.user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )

        track = self.track_repo.find_by_id(command.track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError(
                f"Track with ID {command.track_id} not found or inactive."
            )

        if not user.can_listen(track):
            raise BusinessRuleViolationError(
                "Track is blocked for underage users or violates genre preferences."
            )

        # Enforce max duration cap before adding
        current_duration = playlist.total_duration_seconds
        if (
            playlist.max_duration_seconds is not None
            and current_duration + track.duration_seconds
            > playlist.max_duration_seconds
        ):
            raise BusinessRuleViolationError(
                "Track addition exceeds maximum playlist duration."
            )

        try:
            interaction_action = InteractionAction.parse(
                command.action, default=InteractionAction.LIKE
            )
        except ValueError as exc:
            raise BusinessRuleViolationError(
                "Only likes and superlikes can be added to the playlist."
            ) from exc
        if not interaction_action.is_positive:
            raise BusinessRuleViolationError(
                "Only likes and superlikes can be added to the playlist."
            )

        if self.interaction_repo is not None:
            self.interaction_repo.save(
                Interaction(
                    user_id=command.user_id,
                    track_id=command.track_id,
                    action=interaction_action,
                    source=InteractionSource.PLAYLIST,
                )
            )

        playlist.add_track(track)
        saved_playlist = self.playlist_repo.save(playlist)
        self._record_access(command.user_id, command.track_id)
        return saved_playlist
