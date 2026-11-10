"""User profile and membership presentation schemas."""

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


class AnnualStatsResponse(BaseModel):
    """Aggregated listening statistics and retrospective metrics for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    estimated_listening_hours: float
    total_likes: int
    top_genres: list[str] = Field(default_factory=list)
    top_artists: list[str] = Field(default_factory=list)


__all__ = [
    "AddFamilyMemberRequest",
    "AnnualStatsResponse",
    "BlockedGenresRequest",
    "ChangePlanRequest",
    "FavoriteGenresRequest",
    "LinkSpotifyRequest",
    "ThemePreferenceRequest",
    "UpdateProfileRequest",
    "UserProfileResponse",
]
