"""Use case for uploading and attaching a cover image to a playlist."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.domain.models.playlist import Playlist


@dataclass(slots=True, frozen=True)
class UploadPlaylistCoverUseCase:
    """Uploads and saves a cover image for a user-owned playlist."""

    playlist_repo: PlaylistRepositoryPort

    def execute(
        self,
        playlist_id: int,
        user_id: int,
        content_type: str,
        image_data: bytes,
        cover_image_url: str,
    ) -> Playlist:
        playlist = self.playlist_repo.find_by_id(playlist_id)
        if playlist is None:
            raise EntityNotFoundError(entity_name="Playlist", entity_id=playlist_id)
        if not playlist.is_owned_by(user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )

        saved = self.playlist_repo.save_cover_image(
            playlist_id=playlist_id,
            content_type=content_type,
            image_data=image_data,
            cover_image_url=cover_image_url,
        )
        if not saved:
            raise EntityNotFoundError(entity_name="Playlist", entity_id=playlist_id)

        updated = self.playlist_repo.find_by_id(playlist_id)
        if updated is None:
            raise EntityNotFoundError(entity_name="Playlist", entity_id=playlist_id)
        return updated


__all__ = ["UploadPlaylistCoverUseCase"]
