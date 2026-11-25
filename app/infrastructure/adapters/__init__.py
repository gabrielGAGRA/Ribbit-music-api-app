"""Infrastructure adapters package exporting concrete external service adapters."""

from app.infrastructure.adapters.gcp import (
    FirestoreRestClient,
    FirestoreSyncService,
    GCSTrackCatalogAdapter,
)
from app.infrastructure.adapters.google_auth_adapter import (
    GoogleIdpVerifierAdapter,
    GoogleOAuthAdapter,
)
from app.infrastructure.adapters.itunes_adapter import ITunesAdapter
from app.infrastructure.adapters.spotify import SpotifyAdapter

__all__ = [
    "FirestoreRestClient",
    "FirestoreSyncService",
    "GCSTrackCatalogAdapter",
    "GoogleIdpVerifierAdapter",
    "GoogleOAuthAdapter",
    "ITunesAdapter",
    "SpotifyAdapter",
]
