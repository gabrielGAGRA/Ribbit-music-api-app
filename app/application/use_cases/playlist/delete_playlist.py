"""Use case for deleting a user playlist."""

from dataclasses import dataclass

from app.application.dtos.playlist_dtos import DeletePlaylistCommand
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class DeletePlaylistUseCase:
    """Deletes a playlist owned exclusively by the authenticated user."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort

    def execute(
        self,
        command_or_playlist_id: DeletePlaylistCommand | int,
        user_id: int | None = None,
    ) -> bool:
        if isinstance(command_or_playlist_id, DeletePlaylistCommand):
            playlist_id = command_or_playlist_id.playlist_id
            effective_user_id = command_or_playlist_id.user_id
        else:
            playlist_id = command_or_playlist_id
            if user_id is None:
                raise ValueError(
                    "user_id must be provided when passing playlist_id directly."
                )
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

        return self.playlist_repo.delete(playlist_id)
