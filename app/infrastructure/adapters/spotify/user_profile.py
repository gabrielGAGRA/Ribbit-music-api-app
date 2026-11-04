"""Spotify current user profile adapter."""

import niquests

from app.application.ports.services.spotify import (
    SpotifyUserProfile,
    SpotifyUserProfilePort,
)
from app.domain.exceptions import SpotifyAuthError

_SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"
_HTTP_TIMEOUT_SECONDS = 5.0


class SpotifyUserProfileAdapter(SpotifyUserProfilePort):
    def __init__(self, session: niquests.Session | None = None) -> None:
        self._session = session or niquests.Session()

    def get_current_user_profile(self, access_token: str) -> SpotifyUserProfile:
        if not access_token.strip():
            raise SpotifyAuthError("Spotify access token cannot be blank.")

        try:
            resp = self._session.get(
                _SPOTIFY_ME_URL,
                headers={"Authorization": f"Bearer {access_token.strip()}"},
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise SpotifyAuthError(
                "Unable to fetch Spotify profile due to network failure."
            ) from exc

        if resp.status_code != 200:
            raise SpotifyAuthError(
                f"Failed to fetch Spotify user profile: status {resp.status_code}",
                details={"status_code": resp.status_code},
            )

        data = resp.json()
        user_id = data.get("id")
        if not user_id:
            raise SpotifyAuthError("Spotify profile response missing 'id' field.")

        return SpotifyUserProfile(
            id=user_id,
            display_name=data.get("display_name") or user_id,
            email=data.get("email"),
        )


__all__ = ["SpotifyUserProfileAdapter"]
