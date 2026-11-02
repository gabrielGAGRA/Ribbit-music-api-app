"""Use case for listing all playlists owned by a user."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.playlist import Playlist


@dataclass(slots=True, frozen=True)
class ListUserPlaylistsUseCase:
    """Retrieves all playlists belonging to a specific user."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort

    def execute(self, user_id: int) -> list[Playlist]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        return self.playlist_repo.list_by_user(user_id)
