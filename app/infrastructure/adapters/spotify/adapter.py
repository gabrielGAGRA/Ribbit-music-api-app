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
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.spotify.auth import SpotifyAuth, SpotifyAuthMode
from app.infrastructure.adapters.spotify.catalog import SpotifyCatalog
from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.http import SpotifyHttpClient
from app.infrastructure.adapters.spotify.player import SpotifyPlayer
from app.infrastructure.adapters.spotify.playlists import SpotifyPlaylists
lazy from app.domain.models.track import ExternalTrackId

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
        catalog_auth = (
            SpotifyAuth(
                SpotifyCredentials(
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                ),
                http_session,
            )
            if credentials.client_secret
            else self.auth
        )
        self.catalog = SpotifyCatalog(SpotifyHttpClient(catalog_auth, http_session))
        http = SpotifyHttpClient(self.auth, http_session)
        if self.auth.mode is not SpotifyAuthMode.CLIENT_CREDENTIALS:
            self.playlists = SpotifyPlaylists(http)
            self.player = SpotifyPlayer(http)

    def search_tracks(
        self, query: str, limit: int = 5, offset: int = 0, market: str | None = None
    ) -> list[CatalogTrack]:
        clamped_limit = min(max(1, limit), 10)
        return self._require_catalog().search_tracks(
            query, clamped_limit, offset, market
        )

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
        self,
        account_id: str,
        name: str,
        track_ids: Sequence[ExternalTrackId | str],
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> str:
        """Creates a private playlist in the authorized Spotify account.

        ``account_id`` is informational: Spotify always writes to the account that granted
        the user token. Ids that are not Spotify track ids are skipped.
        """
        playlists = self._playlists_for_tokens(access_token, refresh_token)
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
            raise ExternalServiceError(
                "Spotify credentials are not configured",
                service_name="Spotify",
                details={"error_kind": "auth"},
            )
        return self.catalog

    def _playlists_for_tokens(
        self, access_token: str | None, refresh_token: str | None
    ) -> SpotifyPlaylists:
        if (access_token or refresh_token) and self.auth is not None:
            user_auth = self.auth.for_user_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
            )
            return SpotifyPlaylists(SpotifyHttpClient(user_auth, user_auth.session))
        return self._require_playlists()

    def _require_playlists(self) -> SpotifyPlaylists:
        if self.playlists is None:
            if self.auth is None:
                raise ExternalServiceError(
                    "Spotify credentials are not configured",
                    service_name="Spotify",
                    details={"error_kind": "auth"},
                )
            raise ExternalServiceError(
                "Playlist export needs a user token; configure redirect_uri or "
                "refresh_token",
                service_name="Spotify",
                details={"error_kind": "forbidden"},
            )
        return self.playlists


__all__ = ["SpotifyAdapter"]
