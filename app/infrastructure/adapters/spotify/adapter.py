"""Spotify adapter implementing the catalog, playlist source, and export ports."""

import base64
import logging
import re
from io import BytesIO
lazy from collections.abc import Sequence

import niquests
from PIL import Image, ImageOps

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
_SPOTIFY_COVER_SIZE = (300, 300)
_SPOTIFY_COVER_MAX_BYTES = 256 * 1024
_MAX_COVER_PIXELS = 20_000_000
_SPOTIFY_ID_PATTERN = re.compile(r"[0-9A-Za-z]{22}")
_SPOTIFY_TRACK_REF_PATTERN = re.compile(
    r"(?:spotify:track:|open\.spotify\.com/track/)([0-9A-Za-z]{22})"
)
_logger = logging.getLogger(__name__)


def _encode_spotify_cover(content_type: str, image_data: bytes) -> str:
    normalized_type = content_type.strip().casefold()
    if normalized_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ExternalServiceError(
            "The playlist cover format is not supported by Spotify.",
            service_name="Spotify",
            details={"error_kind": "invalid_cover"},
        )

    try:
        with Image.open(BytesIO(image_data)) as source:
            if source.width * source.height > _MAX_COVER_PIXELS:
                raise ExternalServiceError(
                    "The playlist cover image is too large to export.",
                    service_name="Spotify",
                    details={"error_kind": "invalid_cover"},
                )
            transposed = ImageOps.exif_transpose(source)
            cover = ImageOps.fit(
                (transposed if transposed is not None else source).convert("RGB"),
                _SPOTIFY_COVER_SIZE,
            )
    except (Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ExternalServiceError(
            "The playlist cover could not be processed for Spotify.",
            service_name="Spotify",
            details={"error_kind": "invalid_cover"},
        ) from exc

    for quality in range(90, 9, -10):
        output = BytesIO()
        cover.save(output, format="JPEG", quality=quality, optimize=True)
        jpeg_data = output.getvalue()
        encoded = base64.b64encode(jpeg_data).decode("ascii")
        if len(encoded) <= _SPOTIFY_COVER_MAX_BYTES:
            return encoded

    raise ExternalServiceError(
        "The playlist cover could not be compressed to Spotify's size limit.",
        service_name="Spotify",
        details={"error_kind": "invalid_cover"},
    )


def _extract_spotify_track_id(value: str) -> str | None:
    cleaned = value.strip()
    if _SPOTIFY_ID_PATTERN.fullmatch(cleaned):
        return cleaned
    match = _SPOTIFY_TRACK_REF_PATTERN.search(cleaned)
    return match.group(1) if match else None


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
        cover_image: tuple[str, bytes] | None = None,
        cover_image_base64: str | None = None,
    ) -> str:
        """Creates a private playlist in the authorized Spotify account.

        ``account_id`` is informational: Spotify always writes to the account that granted
        the user token. Ids that are not Spotify track ids are skipped.
        """
        playlists = self._playlists_for_tokens(access_token, refresh_token)
        created = playlists.create_playlist(name)
        uris: list[str] = []
        for track_id in track_ids:
            normalized = _extract_spotify_track_id(str(track_id))
            if normalized is not None:
                uris.append(f"spotify:track:{normalized}")
        for start in range(0, len(uris), _ADD_ITEMS_BATCH_SIZE):
            playlists.add_playlist_items(
                created.external_id, uris[start : start + _ADD_ITEMS_BATCH_SIZE]
            )
        self._upload_cover_if_present(
            playlists,
            created.external_id,
            cover_image=cover_image,
            cover_image_base64=cover_image_base64,
        )
        return created.external_id

    @staticmethod
    def _upload_cover_if_present(
        playlists: SpotifyPlaylists,
        playlist_id: str,
        *,
        cover_image: tuple[str, bytes] | None = None,
        cover_image_base64: str | None = None,
    ) -> None:
        try:
            encoded_cover: str | None = None
            if cover_image is not None:
                encoded_cover = _encode_spotify_cover(cover_image[0], cover_image[1])
            elif (
                cover_image_base64
                and len(cover_image_base64.encode("ascii", errors="ignore"))
                <= _SPOTIFY_COVER_MAX_BYTES
            ):
                encoded_cover = cover_image_base64
            if encoded_cover:
                playlists.upload_playlist_cover(playlist_id, encoded_cover)
        except ExternalServiceError:
            _logger.warning(
                "Failed to upload cover image for Spotify playlist %s",
                playlist_id,
                exc_info=True,
            )

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
