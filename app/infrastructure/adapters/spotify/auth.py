"""Spotify OAuth 2.0 flows (client credentials, authorization code, PKCE) and token lifecycle."""

import base64
import hashlib
import secrets
import threading
import time
from enum import StrEnum
from http import HTTPStatus
from typing import Self
from urllib.parse import urlencode
lazy from collections.abc import Callable, Mapping, Sequence

import niquests

from app.application.ports.services.spotify import SpotifyAuthPort
from app.domain.exceptions import SpotifyAuthError, SpotifyError, SpotifyForbiddenError
from app.infrastructure.adapters.spotify.mappers import map_tokens
lazy from app.application.dtos.spotify_dtos import SpotifyTokens
lazy from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials

HTTP_TIMEOUT_SECONDS = 5.0

_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105
_TOKEN_EXPIRY_MARGIN_SECONDS = 30


class SpotifyAuthMode(StrEnum):
    CLIENT_CREDENTIALS = "client_credentials"
    AUTH_CODE = "auth_code"
    PKCE = "pkce"

    @classmethod
    def from_credentials(cls, credentials: SpotifyCredentials) -> Self:
        has_user_flow = bool(credentials.redirect_uri or credentials.refresh_token)
        if credentials.client_secret and has_user_flow:
            return cls.AUTH_CODE
        if credentials.client_secret:
            return cls.CLIENT_CREDENTIALS
        if credentials.redirect_uri:
            return cls.PKCE
        raise ValueError(
            "client_secret or redirect_uri is required alongside client_id"
        )


class SpotifyAuth(SpotifyAuthPort):
    """Holds credentials and in-memory tokens; refreshes the access token on demand."""

    def __init__(
        self,
        credentials: SpotifyCredentials,
        session: niquests.Session,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._credentials = credentials
        self._session = session
        self._clock = clock
        self._lock = threading.RLock()
        self.mode = SpotifyAuthMode.from_credentials(credentials)
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._refresh_token = credentials.refresh_token
        self._granted_scopes: frozenset[str] | None = None
        self._code_verifier: str | None = None

    def get_authorize_url(self, scopes: Sequence[str], state: str) -> str:
        params = {
            "client_id": self._credentials.client_id,
            "response_type": "code",
            "redirect_uri": self._require_redirect_uri(),
            "scope": " ".join(scopes),
            "state": state,
        }
        if self.mode is SpotifyAuthMode.PKCE:
            self._code_verifier = secrets.token_urlsafe(64)
            digest = hashlib.sha256(self._code_verifier.encode()).digest()
            params["code_challenge_method"] = "S256"
            params["code_challenge"] = (
                base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
            )
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> SpotifyTokens:
        with self._lock:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._require_redirect_uri(),
            }
            if self.mode is SpotifyAuthMode.PKCE:
                if self._code_verifier is None:
                    raise SpotifyAuthError(
                        "code_verifier missing: call get_authorize_url first"
                    )
                data["client_id"] = self._credentials.client_id
                data["code_verifier"] = self._code_verifier
            return self._request_tokens(data)

    def refresh_access_token(self) -> SpotifyTokens:
        with self._lock:
            if self._refresh_token is None:
                raise SpotifyAuthError(
                    "User authorization required: no refresh_token available"
                )
            data = {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
            if self.mode is SpotifyAuthMode.PKCE:
                data["client_id"] = self._credentials.client_id
            return self._request_tokens(data)

    def get_client_credentials_token(self) -> SpotifyTokens:
        with self._lock:
            return self._request_tokens({"grant_type": "client_credentials"})

    def get_access_token(self) -> str:
        with self._lock:
            if (
                self._access_token
                and self._clock() < self._expires_at - _TOKEN_EXPIRY_MARGIN_SECONDS
            ):
                return self._access_token
            if self.mode is SpotifyAuthMode.CLIENT_CREDENTIALS:
                return self.get_client_credentials_token().access_token
            if self._refresh_token is None:
                raise SpotifyAuthError(
                    "User authorization required: call exchange_code first"
                )
            return self.refresh_access_token().access_token

    def require_any_scope(self, scopes: frozenset[str]) -> None:
        """Fails before any HTTP call when none of ``scopes`` is granted."""
        with self._lock:
            if not scopes:
                return
            if self.mode is SpotifyAuthMode.CLIENT_CREDENTIALS:
                raise SpotifyForbiddenError(
                    "Endpoint needs a user token; client credentials carry no scopes",
                    details={"scopes": sorted(scopes)},
                )
            if self._granted_scopes is not None and not scopes & self._granted_scopes:
                raise SpotifyForbiddenError(
                    "None of the required scopes was granted",
                    details={"scopes": sorted(scopes)},
                )

    def invalidate_access_token(self) -> None:
        """Invalidates the cached access token without discarding refresh token or credentials."""
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0

    def clear_tokens(self) -> None:
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0
            self._refresh_token = None
            self._granted_scopes = None

    def _require_redirect_uri(self) -> str:
        if self._credentials.redirect_uri is None:
            raise SpotifyAuthError(
                "redirect_uri is required for the authorization flow"
            )
        return self._credentials.redirect_uri

    def _request_tokens(self, data: Mapping[str, str]) -> SpotifyTokens:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self._credentials.client_secret:
            raw = f"{self._credentials.client_id}:{self._credentials.client_secret}"
            headers["Authorization"] = (
                f"Basic {base64.b64encode(raw.encode()).decode()}"
            )
        try:
            response = self._session.request(
                "POST",
                _TOKEN_URL,
                data=dict(data),
                headers=headers,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except niquests.RequestException as exc:
            raise SpotifyError(
                f"Failed to reach Spotify token endpoint: {exc}"
            ) from exc
        if response.status_code != HTTPStatus.OK:
            self._raise_token_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SpotifyError(
                "Spotify token endpoint returned an unexpected payload"
            ) from exc
        tokens = map_tokens(payload)
        self._store(tokens)
        return tokens

    def _raise_token_error(self, response: niquests.Response) -> None:
        try:
            error = response.json().get("error")
        except (ValueError, AttributeError):  # fmt: skip
            error = None
        if response.status_code == HTTPStatus.BAD_REQUEST and error == "invalid_grant":
            self.clear_tokens()
            raise SpotifyAuthError(
                "invalid_grant: refresh_token expired or revoked; re-authorize the user"
            )
        raise SpotifyError(
            f"Spotify token endpoint returned status {response.status_code}",
            details={"status_code": response.status_code, "error": error},
        )

    def _store(self, tokens: SpotifyTokens) -> None:
        with self._lock:
            self._access_token = tokens.access_token
            self._expires_at = self._clock() + tokens.expires_in
            if tokens.refresh_token:
                self._refresh_token = tokens.refresh_token
            if self.mode is SpotifyAuthMode.CLIENT_CREDENTIALS:
                self._granted_scopes = frozenset()
            elif tokens.scope is not None:
                self._granted_scopes = frozenset(tokens.scope.split())
