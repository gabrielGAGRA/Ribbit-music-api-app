"""Spotify adapter implementing the catalog, playlist source, and export ports."""

import re
lazy from collections.abc import Sequence

import niquests

from app.application.ports.services.music_service import (
    CatalogTrack,
    PlaylistExportPort,
    PlaylistItemsPage,
    PlaylistSourcePort,
    ProviderPlaylist,
    TrackCatalogPort,
)
from app.domain.exceptions import SpotifyAuthError, SpotifyForbiddenError
from app.infrastructure.adapters.spotify.auth import SpotifyAuth, SpotifyAuthMode
from app.infrastructure.adapters.spotify.catalog import SpotifyCatalog
from app.infrastructure.adapters.spotify.http import SpotifyHttpClient
from app.infrastructure.adapters.spotify.player import SpotifyPlayer
from app.infrastructure.adapters.spotify.playlists import SpotifyPlaylists
lazy from app.domain.models.track import ExternalTrackId
lazy from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials

_ADD_ITEMS_BATCH_SIZE = 100
_SPOTIFY_ID_PATTERN = re.compile(r"[0-9A-Za-z]{22}")


class SpotifyAdapter(TrackCatalogPort, PlaylistExportPort, PlaylistSourcePort):
    """Facade over the Spotify modules the credential type allows.

    Without credentials the adapter is disabled: searches return no tracks and exports
    fail. Client credentials expose only the catalog; ``playlists`` and ``player`` need a
    user flow (authorization code or PKCE) because ``/me/*`` routes require user tokens.
    """

    def __init__(
        self,
        credentials: SpotifyCredentials | None = None,
        session: niquests.Session | None = None,
    ) -> None:
        self.auth: SpotifyAuth | None = None
        self.catalog: SpotifyCatalog | None = None
        self.playlists: SpotifyPlaylists | None = None
        self.player: SpotifyPlayer | None = None
        if credentials is None:
            return
        http_session = session or niquests.Session()
        self.auth = SpotifyAuth(credentials, http_session)
        http = SpotifyHttpClient(self.auth, http_session)
        self.catalog = SpotifyCatalog(http)
        if self.auth.mode is not SpotifyAuthMode.CLIENT_CREDENTIALS:
            self.playlists = SpotifyPlaylists(http)
            self.player = SpotifyPlayer(http)

    def search_tracks(
        self, query: str, limit: int = 5, offset: int = 0, market: str | None = None
    ) -> list[CatalogTrack]:
        return self._require_catalog().search_tracks(query, limit, offset, market)

    def get_track(self, track_id: str, market: str | None = None) -> CatalogTrack:
        return self._require_catalog().get_track(track_id, market)

    def get_playlist(
        self, playlist_id: str, market: str | None = None
    ) -> ProviderPlaylist:
        return self._require_playlists().get_playlist(playlist_id, market)

    def get_playlist_items(
        self,
        playlist_id: str,
        limit: int = 50,
        offset: int = 0,
        market: str | None = None,
    ) -> PlaylistItemsPage:
        return self._require_playlists().get_playlist_items(
            playlist_id, limit, offset, market
        )

    def export_playlist(
        self, account_id: str, name: str, track_ids: Sequence[ExternalTrackId | str]
    ) -> str:
        """Creates a private playlist in the authorized Spotify account.

        ``account_id`` is informational: Spotify always writes to the account that granted
        the user token. Ids that are not Spotify track ids are skipped.
        """
        playlists = self._require_playlists()
        created = playlists.create_playlist(name)
        uris = [
            f"spotify:track:{track_id}"
            for track_id in track_ids
            if _SPOTIFY_ID_PATTERN.fullmatch(track_id)
        ]
        for start in range(0, len(uris), _ADD_ITEMS_BATCH_SIZE):
            playlists.add_playlist_items(
                created.external_id, uris[start : start + _ADD_ITEMS_BATCH_SIZE]
            )
        return created.external_id

    def _require_catalog(self) -> SpotifyCatalog:
        if self.catalog is None:
            raise SpotifyAuthError("Spotify credentials are not configured")
        return self.catalog

    def _require_playlists(self) -> SpotifyPlaylists:
        if self.playlists is None:
            if self.auth is None:
                raise SpotifyAuthError("Spotify credentials are not configured")
            raise SpotifyForbiddenError(
                "Playlist export needs a user token; configure redirect_uri or "
                "refresh_token"
            )
        return self.playlists


__all__ = ["SpotifyAdapter"]
