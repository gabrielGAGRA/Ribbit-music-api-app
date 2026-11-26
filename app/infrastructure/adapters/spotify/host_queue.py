"""User-scoped adapter wiring SpotifyPlayer to a pond owner's stored OAuth tokens."""

from datetime import UTC, datetime

lazy import niquests

from app.application.ports.services.spotify import (
    SpotifyHostQueuePort,
    SpotifyQueuePort,
)
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.spotify.auth import SpotifyAuth
from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.http import SpotifyHttpClient
from app.infrastructure.adapters.spotify.player import SpotifyPlayer
lazy from app.domain.models.user import User

_READ_DEVICES_SCOPES = frozenset({"user-read-playback-state"})


class SpotifyHostQueueAdapter(SpotifyHostQueuePort):
    """Creates per-user SpotifyPlayer instances from persisted OAuth tokens."""

    def __init__(
        self,
        credentials: SpotifyCredentials,
        session: niquests.Session,
    ) -> None:
        self._credentials = credentials
        self._session = session

    def _build_client(self, user: User) -> SpotifyHttpClient:
        creds = SpotifyCredentials(
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            redirect_uri=self._credentials.redirect_uri,
            refresh_token=user.spotify_refresh_token,
        )
        auth = SpotifyAuth(creds, session=self._session)
        if user.spotify_access_token:
            remaining = 3600.0
            if user.spotify_token_expires_at is not None:
                expires_at = (
                    user.spotify_token_expires_at
                    if user.spotify_token_expires_at.tzinfo is not None
                    else user.spotify_token_expires_at.replace(tzinfo=UTC)
                )
                remaining = (expires_at - datetime.now(UTC)).total_seconds()
            if remaining > 0:
                auth.seed_tokens(
                    user.spotify_access_token,
                    remaining,
                    refresh_token=user.spotify_refresh_token,
                )
        return SpotifyHttpClient(auth=auth, session=self._session)

    def _build_player(self, user: User) -> SpotifyQueuePort:
        return SpotifyPlayer(self._build_client(user))

    def _pick_fallback_device_id(self, http: SpotifyHttpClient) -> str | None:
        data = http.request("GET", "/me/player/devices", scopes=_READ_DEVICES_SCOPES)
        devices = data.get("devices") if isinstance(data, dict) else None
        if not isinstance(devices, list):
            return None
        candidates = [
            d
            for d in devices
            if isinstance(d, dict)
            and isinstance(d.get("id"), str)
            and d.get("id")
            and not d.get("is_restricted")
        ]
        if not candidates:
            return None
        for d in candidates:
            if d.get("is_active"):
                return str(d["id"])
        for d in candidates:
            if d.get("type") == "Computer":
                return str(d["id"])
        return str(candidates[0]["id"])

    def enqueue_track(self, user: User, track_uri: str) -> None:
        http = self._build_client(user)
        player = SpotifyPlayer(http)
        try:
            player.add_to_queue(track_uri)
        except ExternalServiceError as exc:
            if exc.details.get("status_code") != 404:
                raise
            device_id = self._pick_fallback_device_id(http)
            if not device_id:
                raise
            player.add_to_queue(track_uri, device_id=device_id)

    def skip_to_next(self, user: User) -> None:
        self._build_player(user).next_track()

    def start_track(self, user: User, track_uri: str) -> None:
        self._build_player(user).play(uris=[track_uri])


__all__ = ["SpotifyHostQueueAdapter"]
