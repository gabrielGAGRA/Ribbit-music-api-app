"""Infrastructure adapters package exporting concrete external service adapters."""

from app.infrastructure.adapters.gcp import GCSTrackCatalogAdapter
from app.infrastructure.adapters.itunes_adapter import ITunesAdapter
from app.infrastructure.adapters.spotify_adapter import SpotifyAdapter

__all__ = ["GCSTrackCatalogAdapter", "ITunesAdapter", "SpotifyAdapter"]
