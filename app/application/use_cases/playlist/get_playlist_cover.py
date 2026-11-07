"""Use case for retrieving a playlist cover image."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)


@dataclass(slots=True, frozen=True)
class GetPlaylistCoverUseCase:
    """Retrieves the content type and binary data of a playlist cover."""

    playlist_repo: PlaylistRepositoryPort

    def execute(self, playlist_id: int, user_id: int) -> tuple[str, bytes]:
        playlist = self.playlist_repo.find_by_id(playlist_id)
        if playlist is None:
            raise EntityNotFoundError(entity_name="Playlist", entity_id=playlist_id)
        if not playlist.is_owned_by(user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )

        image = self.playlist_repo.get_cover_image(playlist_id)
        if image is None:
            raise EntityNotFoundError("Playlist cover image not found.")
        return image


__all__ = ["GetPlaylistCoverUseCase"]
