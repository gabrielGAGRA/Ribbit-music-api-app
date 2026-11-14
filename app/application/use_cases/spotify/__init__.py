"""Spotify integration and synchronization use cases."""

from app.application.use_cases.spotify.connect_spotify_account import (
    ConnectSpotifyAccountUseCase,
)
from app.application.use_cases.spotify.get_spotify_authorize_url import (
    GetSpotifyAuthorizeUrlUseCase,
)
from app.application.use_cases.spotify.premium_guard import (
    execute_with_spotify_premium,
    require_spotify_premium,
)
from app.application.use_cases.spotify.sync_playlist_from_spotify import (
    SyncPlaylistFromSpotifyUseCase,
)
from app.application.use_cases.spotify.sync_tracks_from_spotify import (
    SyncTracksFromSpotifyUseCase,
)

__all__ = [
    "ConnectSpotifyAccountUseCase",
    "GetSpotifyAuthorizeUrlUseCase",
    "SyncPlaylistFromSpotifyUseCase",
    "SyncTracksFromSpotifyUseCase",
    "execute_with_spotify_premium",
    "require_spotify_premium",
]
