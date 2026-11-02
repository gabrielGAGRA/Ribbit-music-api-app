"""Use case for importing a Spotify playlist and its tracks for a user."""

from dataclasses import dataclass

from app.application.use_cases.spotify.helpers import upsert_catalog_track
from app.domain.exceptions import EntityNotFoundError
lazy from app.application.dtos.spotify_dtos import SyncPlaylistFromSpotifyCommand
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import PlaylistSourcePort
lazy from app.domain.models.playlist import Playlist
lazy from app.domain.models.track import Track

_PAGE_SIZE = 50


@dataclass(slots=True, frozen=True)
class SyncPlaylistFromSpotifyUseCase:
    """Imports a Spotify playlist, updating the user's copy if it was imported before."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    source: PlaylistSourcePort

    def execute(self, command: SyncPlaylistFromSpotifyCommand) -> Playlist:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        remote = self.source.get_playlist(command.spotify_playlist_id)
        tracks = self._import_tracks(command)

        existing = next(
            (
                playlist
                for playlist in self.playlist_repo.list_by_user(command.user_id)
                if playlist.spotify_playlist_id == remote.external_id
            ),
            None,
        )
        if existing is None:
            playlist = Playlist(
                user_id=command.user_id,
                name=remote.name,
                description=remote.description,
                spotify_playlist_id=remote.external_id,
                initial_tracks=tracks,
            )
        else:
            playlist = existing.replace_tracks(tracks)
        return self.playlist_repo.save(playlist)

    def _import_tracks(self, command: SyncPlaylistFromSpotifyCommand) -> list[Track]:
        tracks: dict[int, Track] = {}
        offset = 0
        while offset < command.max_items:
            limit = min(_PAGE_SIZE, command.max_items - offset)
            page = self.source.get_playlist_items(
                command.spotify_playlist_id, limit=limit, offset=offset
            )
            for catalog_track in page.items:
                track = upsert_catalog_track(
                    self.track_repo, catalog_track, command.genre
                )
                if track is not None and track.track_id is not None:
                    tracks.setdefault(track.track_id, track)
            if page.raw_item_count == 0 or page.raw_item_count < limit:
                break
            offset += page.raw_item_count
            if page.total > 0 and offset >= page.total:
                break
        return list(tracks.values())


__all__ = ["SyncPlaylistFromSpotifyUseCase"]
