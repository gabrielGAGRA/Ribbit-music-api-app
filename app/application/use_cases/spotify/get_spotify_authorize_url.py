"""Use case for generating Spotify OAuth authorization URL."""

from dataclasses import dataclass
from typing import ClassVar

lazy from app.application.ports.services.spotify import SpotifyAuthPort


@dataclass(slots=True, frozen=True)
class GetSpotifyAuthorizeUrlUseCase:
    """Generates the Spotify authorization URL with standard platform scopes."""

    DEFAULT_SCOPES: ClassVar[tuple[str, ...]] = (
        "user-read-private",
        "user-read-email",
        "playlist-read-private",
        "playlist-modify-public",
        "playlist-modify-private",
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
    )

    spotify_auth: SpotifyAuthPort

    def execute(self, state: str = "") -> str:
        return self.spotify_auth.get_authorize_url(self.DEFAULT_SCOPES, state)


__all__ = ["GetSpotifyAuthorizeUrlUseCase"]
