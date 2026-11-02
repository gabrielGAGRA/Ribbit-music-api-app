"""Use case for exporting a playlist to an external Spotify account."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import PlaylistExportPort
lazy from app.domain.models.playlist import Playlist


@dataclass(slots=True, frozen=True)
class ExportPlaylistToSpotifyUseCase:
    """Exports a user playlist to Spotify using external integration."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    export_port: PlaylistExportPort

    def execute(self, user_id: int, playlist_id: int) -> Playlist:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if not user.spotify_id:
            raise BusinessRuleViolationError(
                "User does not have a linked Spotify account."
            )

        playlist = self.playlist_repo.find_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError(f"Playlist with ID {playlist_id} not found.")

        if not playlist.is_owned_by(user_id):
            raise PermissionDeniedError(
                "Access denied: cannot export a playlist that does not belong to you."
            )

        external_track_ids = [t.spotify_id or str(t.track_id) for t in playlist.tracks]
        spotify_playlist_id = self.export_port.export_playlist(
            account_id=user.spotify_id,
            name=playlist.name,
            track_ids=external_track_ids,
        )

        playlist.export(spotify_playlist_id)
        return self.playlist_repo.save(playlist)
