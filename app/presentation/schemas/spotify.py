"""Schemas for Spotify authorization and connection endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class SpotifyAuthorizeUrlResponse(BaseModel):
    """Payload returning the generated Spotify authorization URL."""

    model_config = ConfigDict(from_attributes=True)

    authorization_url: str


class SpotifyConnectCallbackRequest(BaseModel):
    """Payload containing Spotify authorization code to link user account."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


__all__ = ["SpotifyAuthorizeUrlResponse", "SpotifyConnectCallbackRequest"]
