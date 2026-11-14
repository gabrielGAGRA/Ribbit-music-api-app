"""Spotify Web API HTTP client: token injection, 429 handling, and error mapping."""

import time
from http import HTTPStatus
from typing import Any
lazy from collections.abc import Callable, Mapping

import niquests

from app.domain.exceptions import (
    SpotifyAuthError,
    SpotifyError,
    SpotifyForbiddenError,
    SpotifyPremiumRequiredError,
    SpotifyQuotaExceededError,
)
from app.infrastructure.adapters.spotify.auth import HTTP_TIMEOUT_SECONDS, SpotifyAuth
from app.infrastructure.adapters.spotify.mappers import drop_none

_API_BASE_URL = "https://api.spotify.com/v1"
_MAX_RATE_LIMIT_RETRIES = 3
_DEFAULT_RETRY_AFTER_SECONDS = 1
_MAX_RETRY_AFTER_SECONDS = 30.0


class SpotifyHttpClient:
    def __init__(
        self,
        auth: SpotifyAuth,
        session: niquests.Session,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._auth = auth
        self._session = session
        self._sleep = sleep

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: str | None = None,
        content_type: str | None = None,
        scopes: frozenset[str] = frozenset(),
    ) -> Any | None:
        """Calls the API; ``scopes`` means at least one of them must be granted.

        Returns None for empty responses. Honors ``Retry-After`` on 429 up to a bounded
        number of retries, but fails immediately when the Development quota is exhausted.
        """
        self._auth.get_access_token()
        self._auth.require_any_scope(scopes)
        kwargs: dict[str, Any] = {"timeout": HTTP_TIMEOUT_SECONDS}
        if params:
            kwargs["params"] = drop_none(params)
        if json is not None:
            kwargs["json"] = json
        if data is not None:
            kwargs["data"] = data
        retries = 0
        refreshed_on_unauthorized = False
        while True:
            response = self._send(
                method, path, content_type or "application/json", kwargs
            )
            if (
                response.status_code == HTTPStatus.UNAUTHORIZED
                and not refreshed_on_unauthorized
            ):
                refreshed_on_unauthorized = True
                self._auth.invalidate_access_token()
                try:
                    self._auth.get_access_token()
                except SpotifyAuthError:
                    SpotifyHttpClient._raise_for_status(HTTPStatus.UNAUTHORIZED)
                continue
            if response.status_code != HTTPStatus.TOO_MANY_REQUESTS:
                return self._parse(response)
            self._raise_if_quota_exceeded(response)
            if retries >= _MAX_RATE_LIMIT_RETRIES:
                raise SpotifyError(
                    "Spotify rate limit persisted after retries", details={"path": path}
                )
            retries += 1
            self._sleep(self._retry_after(response))

    def _send(
        self, method: str, path: str, content_type: str, kwargs: dict[str, Any]
    ) -> niquests.Response:
        headers = {
            "Authorization": f"Bearer {self._auth.get_access_token()}",
            "Content-Type": content_type,
        }
        try:
            return self._session.request(
                method, f"{_API_BASE_URL}{path}", headers=headers, **kwargs
            )
        except niquests.RequestException as exc:
            raise SpotifyError(
                f"Failed to communicate with Spotify API: {exc}", details={"path": path}
            ) from exc

    @staticmethod
    def _parse(response: niquests.Response) -> Any | None:
        status = response.status_code or 0
        if status == HTTPStatus.NO_CONTENT:
            return None
        if status >= HTTPStatus.BAD_REQUEST:
            SpotifyHttpClient._raise_for_status(status, response)
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _parse_error_payload(
        response: niquests.Response | None,
    ) -> tuple[str | None, str | None]:
        if response is None:
            return None, None
        try:
            payload = response.json()
        except (ValueError, AttributeError):  # fmt: skip
            return None, None
        if not isinstance(payload, Mapping):
            return None, None
        error = payload.get("error")
        if not isinstance(error, Mapping):
            return None, None
        reason = error.get("reason")
        message = error.get("message")
        return (
            reason.strip() if isinstance(reason, str) and reason.strip() else None,
            message.strip() if isinstance(message, str) and message.strip() else None,
        )

    @staticmethod
    def _raise_for_status(
        status: int, response: niquests.Response | None = None
    ) -> None:
        details: dict[str, Any] = {"status_code": status}
        if status == HTTPStatus.UNAUTHORIZED:
            raise SpotifyAuthError(
                "Spotify rejected the access token; re-authorize the user",
                details=details,
            )
        if status == HTTPStatus.FORBIDDEN:
            reason, message = SpotifyHttpClient._parse_error_payload(response)
            if (reason and reason.casefold() == "premium_required") or (
                reason is None and message and "premium required" in message.casefold()
            ):
                details["reason"] = reason or "PREMIUM_REQUIRED"
                raise SpotifyPremiumRequiredError(
                    "Spotify denied access: Premium subscription required",
                    details=details,
                )
            raise SpotifyForbiddenError(
                "Spotify denied access: scope missing, user not allowlisted, or no Premium",
                details=details,
            )
        raise SpotifyError(f"Spotify API returned status {status}", details=details)

    @staticmethod
    def _raise_if_quota_exceeded(response: niquests.Response) -> None:
        reason, _ = SpotifyHttpClient._parse_error_payload(response)
        if reason == "QUOTA_EXCEEDED":
            raise SpotifyQuotaExceededError("Spotify Development-mode quota exceeded")

    @staticmethod
    def _retry_after(response: niquests.Response) -> float:
        try:
            seconds = float(
                response.headers.get("Retry-After", _DEFAULT_RETRY_AFTER_SECONDS)
            )
        except ValueError:
            return _DEFAULT_RETRY_AFTER_SECONDS
        return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)
