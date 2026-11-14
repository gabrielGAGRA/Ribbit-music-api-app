"""Spotify Web API adapter modules."""

from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.host_queue import SpotifyHostQueueAdapter

__all__ = ["SpotifyCredentials", "SpotifyHostQueueAdapter"]
