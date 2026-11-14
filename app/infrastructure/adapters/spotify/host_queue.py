"""User-scoped adapter wiring SpotifyPlayer to a pond owner's stored OAuth tokens."""

from datetime import UTC, datetime

lazy import niquests

from app.application.ports.services.spotify import (
    SpotifyHostQueuePort,
    SpotifyQueuePort,
)
from app.infrastructure.adapters.spotify.auth import SpotifyAuth
from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.http import SpotifyHttpClient
from app.infrastructure.adapters.spotify.player import SpotifyPlayer
lazy from app.domain.models.user import User


class SpotifyHostQueueAdapter(SpotifyHostQueuePort):
    """Creates per-user SpotifyPlayer instances from persisted OAuth tokens."""

    def __init__(
        self,
        credentials: SpotifyCredentials,
        session: niquests.Session,
    ) -> None:
        self._credentials = credentials
        self._session = session

    def _build_player(self, user: User) -> SpotifyQueuePort:
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
        http = SpotifyHttpClient(auth=auth, session=self._session)
        return SpotifyPlayer(http)

    def enqueue_track(self, user: User, track_uri: str) -> None:
        self._build_player(user).add_to_queue(track_uri)

    def skip_to_next(self, user: User) -> None:
        self._build_player(user).next_track()

    def start_track(self, user: User, track_uri: str) -> None:
        self._build_player(user).play(uris=[track_uri])


__all__ = ["SpotifyHostQueueAdapter"]
