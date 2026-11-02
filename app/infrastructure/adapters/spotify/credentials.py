"""Spotify application credentials value object."""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(slots=True, frozen=True, kw_only=True)
class SpotifyCredentials:
    client_id: str
    client_secret: str | None = None
    redirect_uri: str | None = None
    refresh_token: str | None = None

    def __post_init__(self) -> None:
        if self.redirect_uri is None:
            return
        parsed = urlparse(self.redirect_uri)
        is_loopback_ip = parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
        if parsed.scheme != "https" and not is_loopback_ip:
            raise ValueError(
                "redirect_uri must use https or http://127.0.0.1:PORT, not localhost"
            )
