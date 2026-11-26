"""Use case for exporting a playlist to an external Spotify account."""

import logging
from dataclasses import dataclass

from app.domain.exceptions import (
    EntityNotFoundError,
    ExternalServiceError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import (
    PlaylistExportPort,
    TrackCatalogPort,
)
lazy from app.domain.models.playlist import Playlist
lazy from app.domain.models.track import Track

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ExportPlaylistToSpotifyUseCase:
    """Exports a user playlist to Spotify using external integration."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    export_port: PlaylistExportPort
    track_catalog: TrackCatalogPort | None = None
    track_repo: TrackRepositoryPort | None = None

    def execute(self, user_id: int, playlist_id: int) -> Playlist:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if not user.spotify_id:
            raise PermissionDeniedError(
                "Conecte sua conta do Spotify para exportar playlists.",
                details={"rule_name": "spotify_connection_required"},
            )

        playlist = self.playlist_repo.find_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError(f"Playlist with ID {playlist_id} not found.")

        if not playlist.is_owned_by(user_id):
            raise PermissionDeniedError(
                "Access denied: cannot export a playlist that does not belong to you."
            )

        external_track_ids = [
            self._resolve_track_id(track) for track in playlist.tracks
        ]
        cover_image = self._resolve_cover_image(playlist_id)

        try:
            if cover_image is not None:
                spotify_playlist_id = self.export_port.export_playlist(
                    account_id=user.spotify_id,
                    name=playlist.name,
                    track_ids=external_track_ids,
                    access_token=user.spotify_access_token,
                    refresh_token=user.spotify_refresh_token,
                    cover_image=cover_image,
                )
            else:
                spotify_playlist_id = self.export_port.export_playlist(
                    account_id=user.spotify_id,
                    name=playlist.name,
                    track_ids=external_track_ids,
                    access_token=user.spotify_access_token,
                    refresh_token=user.spotify_refresh_token,
                )
        except ExternalServiceError as exc:
            if exc.details.get("error_kind") in ("auth", "forbidden"):
                raise PermissionDeniedError(
                    "Conecte sua conta do Spotify para exportar playlists.",
                    details={"rule_name": "spotify_connection_required"},
                ) from exc
            raise

        playlist.export(spotify_playlist_id)
        return self.playlist_repo.save(playlist)

    def _resolve_track_id(self, track: Track) -> str:
        if track.spotify_id and track.spotify_id.strip():
            return track.spotify_id.strip()
        if self.track_catalog is not None:
            query = f"{track.title} {track.artist}".strip()
            if query:
                try:
                    matches = self.track_catalog.search_tracks(query, limit=1)
                except ExternalServiceError:
                    _logger.warning(
                        "Failed to resolve Spotify ID for track %s (%s)",
                        track.track_id,
                        query,
                        exc_info=True,
                    )
                    return str(track.track_id)
                if matches and matches[0].external_id:
                    resolved_id = str(matches[0].external_id).strip()
                    if resolved_id:
                        if self.track_repo is not None and track.merge_missing_metadata(
                            spotify_id=resolved_id
                        ):
                            self.track_repo.save(track)
                        return resolved_id
        return str(track.track_id)

    def _resolve_cover_image(self, playlist_id: int) -> tuple[str, bytes] | None:
        image = self.playlist_repo.get_cover_image(playlist_id)
        if (
            not isinstance(image, tuple)
            or len(image) != 2
            or not isinstance(image[0], str)
            or not isinstance(image[1], (bytes, bytearray))
        ):
            return None
        return (image[0], bytes(image[1]))
