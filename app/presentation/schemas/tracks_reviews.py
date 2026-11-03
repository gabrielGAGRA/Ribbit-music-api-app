"""Review presentation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.schemas.discovery import InteractionResponse


class PublishReviewRequest(BaseModel):
    """Payload to post a star rating and critique on a track."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    rating: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    """Public representation of a user review."""

    model_config = ConfigDict(from_attributes=True)

    review_id: int | None = None
    user_id: int
    track_id: int
    rating: int
    text: str | None = None
    likes_count: int = 0
    is_deleted: bool = False
    created_at: datetime | None = None


class CatalogTrackResponse(BaseModel):
    """Public representation of a catalog track with multi-language aliases."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    title: str
    artist: str
    duration_seconds: int
    genre: str
    spotify_id: str | None = None
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    explicit: bool = False
    is_deleted: bool = False


class RecentInteractedTrackResponse(BaseModel):
    """Response item pairing an interaction with the track details."""

    model_config = ConfigDict(from_attributes=True)

    interaction: InteractionResponse
    track: CatalogTrackResponse


class SaveSearchTrackLikeRequest(BaseModel):
    """Payload to save a search track into favorites and optional playlist."""

    playlist_id: int | None = None


class ReviewActionResponse(BaseModel):
    """Generic action response for reviews endpoints."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True


__all__ = [
    "CatalogTrackResponse",
    "PublishReviewRequest",
    "RecentInteractedTrackResponse",
    "ReviewActionResponse",
    "ReviewResponse",
    "SaveSearchTrackLikeRequest",
]
