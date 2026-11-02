"""Use case for feeding the track catalog from a Spotify search."""

from dataclasses import dataclass

from app.application.use_cases.spotify.helpers import upsert_catalog_track
lazy from app.application.dtos.spotify_dtos import SyncTracksFromSpotifyCommand
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.music_service import TrackCatalogPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class SyncTracksFromSpotifyUseCase:
    """Imports the tracks matching a Spotify search into the local catalog."""

    catalog: TrackCatalogPort
    track_repo: TrackRepositoryPort

    def execute(self, command: SyncTracksFromSpotifyCommand) -> list[Track]:
        found = self.catalog.search_tracks(
            command.query, limit=command.limit, offset=command.offset
        )
        saved = (
            upsert_catalog_track(self.track_repo, track, command.genre)
            for track in found
        )
        return [track for track in saved if track is not None]


__all__ = ["SyncTracksFromSpotifyUseCase"]
