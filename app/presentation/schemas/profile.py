"""User profile and membership presentation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.schemas.admin import PlanResponse
from app.presentation.schemas.auth import UserResponse
from app.presentation.schemas.discovery import InteractionResponse


class UpdateProfileRequest(BaseModel):
    """Payload to revise display name or password credentials."""

    display_name: str | None = Field(default=None, min_length=2, max_length=50)
    new_password: str | None = Field(default=None, min_length=6)
    current_password: str | None = Field(default=None)


class LinkSpotifyRequest(BaseModel):
    """Payload to associate a third-party Spotify identifier."""

    model_config = ConfigDict(extra="forbid")

    spotify_id: str


class ChangePlanRequest(BaseModel):
    """Payload to switch subscription plan tier."""

    model_config = ConfigDict(extra="forbid")

    new_plan_id: int


class BlockedGenresRequest(BaseModel):
    """Payload to update blocked music genres."""

    model_config = ConfigDict(extra="forbid")

    blocked_genres: str | list[str]


class FavoriteGenresRequest(BaseModel):
    """Payload to update favorite music genres."""

    model_config = ConfigDict(extra="forbid")

    favorite_genres: str | list[str]


class ThemePreferenceRequest(BaseModel):
    """Payload to update the user's preferred interface theme."""

    model_config = ConfigDict(extra="forbid")

    preferred_theme: str


class AddFamilyMemberRequest(BaseModel):
    """Payload to link or provision a dependent profile under a primary account."""

    model_config = ConfigDict(extra="forbid")

    dependent_user_id: int | None = None
    email: str | None = None
    password: str | None = None
    display_name: str | None = None
    birth_date: str | None = None
    age: int = 0


class UserProfileResponse(BaseModel):
    """Composite presentation of a user profile along with active plan details and history."""

    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    plan: PlanResponse
    recent_interactions: list[InteractionResponse] = Field(default_factory=list)


class GenreStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    genre: str
    likes: int
    superlikes: int
    dislikes: int
    total_positive: int


class ArtistStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artist: str
    likes: int
    superlikes: int
    dislikes: int
    total_positive: int
    cover_url: str | None = None


class YearlyInteractionStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    likes: int
    superlikes: int
    dislikes: int
    total: int


class MonthlyInteractionStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: int
    likes: int
    superlikes: int
    dislikes: int
    total: int


class ReleaseYearStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    release_year: int
    likes: int
    superlikes: int
    total_positive: int


class SourceStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    likes: int
    superlikes: int
    dislikes: int
    total: int


class AnnualStatsResponse(BaseModel):
    """Aggregated listening statistics and retrospective metrics for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    year: int | None = None
    available_years: list[int] = Field(default_factory=list)
    total_interactions: int = 0
    total_likes: int = 0
    total_superlikes: int = 0
    total_dislikes: int = 0
    positive_rate: float = 0.0
    top_genres: list[GenreStatResponse] = Field(default_factory=list)
    top_artists: list[ArtistStatResponse] = Field(default_factory=list)
    by_interaction_year: list[YearlyInteractionStatResponse] = Field(
        default_factory=list
    )
    by_month: list[MonthlyInteractionStatResponse] = Field(default_factory=list)
    by_release_year: list[ReleaseYearStatResponse] = Field(default_factory=list)
    by_source: list[SourceStatResponse] = Field(default_factory=list)
    total_reviews: int = 0
    average_rating: float = 0.0
    total_playlists: int = 0
    total_jams_participated: int = 0


class UserTrackAccessResponse(BaseModel):
    """Listener-facing track access history item."""

    model_config = ConfigDict(from_attributes=True)

    access_id: int
    user_id: int
    track_id: int
    track_title: str
    track_artist: str
    track_genre: str
    track_album: str | None = None
    track_duration_seconds: int = 0
    track_cover_url: str | None = None
    track_preview_url: str | None = None
    track_explicit: bool = False
    source: str
    accessed_at: datetime


class UserAccessHistoryResponse(BaseModel):
    """Response containing active access history and distinct seen track IDs."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UserTrackAccessResponse] = Field(default_factory=list)
    seen_track_ids: list[int] = Field(default_factory=list)


__all__ = [
    "AddFamilyMemberRequest",
    "AnnualStatsResponse",
    "ArtistStatResponse",
    "BlockedGenresRequest",
    "ChangePlanRequest",
    "FavoriteGenresRequest",
    "GenreStatResponse",
    "LinkSpotifyRequest",
    "MonthlyInteractionStatResponse",
    "ReleaseYearStatResponse",
    "SourceStatResponse",
    "ThemePreferenceRequest",
    "UpdateProfileRequest",
    "UserAccessHistoryResponse",
    "UserProfileResponse",
    "UserTrackAccessResponse",
    "YearlyInteractionStatResponse",
]
