"""Use case for removing a track from a playlist."""

from dataclasses import dataclass

from app.application.dtos.playlist_dtos import RemoveTrackFromPlaylistCommand
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class RemoveTrackFromPlaylistUseCase:
    """Removes a track exclusively from a playlist owned by the authenticated user."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort

    def execute(
        self,
        command_or_playlist_id: RemoveTrackFromPlaylistCommand | int,
        track_id: int | None = None,
        user_id: int | None = None,
    ) -> bool:
        if isinstance(command_or_playlist_id, RemoveTrackFromPlaylistCommand):
            playlist_id = command_or_playlist_id.playlist_id
            target_track_id = command_or_playlist_id.track_id
            effective_user_id = command_or_playlist_id.user_id
        else:
            playlist_id = command_or_playlist_id
            if track_id is None or user_id is None:
                raise ValueError(
                    "track_id and user_id must be provided when passing playlist_id directly."
                )
            target_track_id = track_id
            effective_user_id = user_id

        user = self.user_repo.find_by_id(effective_user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {effective_user_id} not found.")

        playlist = self.playlist_repo.find_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError(f"Playlist with ID {playlist_id} not found.")

        if not playlist.is_owned_by(effective_user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )

        if not any(t.track_id == target_track_id for t in playlist.tracks):
            raise EntityNotFoundError(
                f"Track with ID {target_track_id} not found in playlist."
            )

        return self.playlist_repo.remove_track(playlist_id, target_track_id)
