"""Administrative presentation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanResponse(BaseModel):
    """Public representation of a subscription plan."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: int
    name: str
    monthly_price: float
    max_profiles: int


class UpdatePlanAdminRequest(BaseModel):
    """Payload for modifying an existing subscription plan tier."""

    model_config = ConfigDict(extra="forbid")

    new_price: float | None = None
    new_name: str | None = None
    max_profiles: int | None = None


class UpdateTrackExplicitRequest(BaseModel):
    """Payload to alter a track explicit advisory status."""

    explicit: bool


class BlockTrackRequest(BaseModel):
    """Payload for toggling track block state."""

    model_config = ConfigDict(extra="forbid")

    blocked: bool | None = None


class TrackBlockResponse(BaseModel):
    """Response returned upon blocking or unblocking a catalog track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int | None = None
    blocked: bool


class TrackExplicitResponse(BaseModel):
    """Response returned upon updating explicit status on a track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    explicit: bool


class ExecutiveDashboardResponse(BaseModel):
    """Aggregated platform performance and subscription revenue metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int] = Field(default_factory=dict)
    revenue_by_plan: dict[str, float] = Field(default_factory=dict)
    gross_revenue: float = 0.0
    content_cost: float = 0.0
    infrastructure_cost: float = 0.0
    total_costs: float = 0.0
    active_tracks_count: int = 0
    content_cost_per_track: float = 0.0
    infrastructure_fixed_cost: float = 0.0
    infrastructure_cost_per_user: float = 0.0


class TrackAccessRankResponse(BaseModel):
    """Ranked track access count item."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    title: str
    artist: str
    is_deleted: bool = False
    access_count: int


class GenreAccessCountResponse(BaseModel):
    """Aggregated genre access count item."""

    model_config = ConfigDict(from_attributes=True)

    genre: str
    access_count: int


class AudienceReportResponse(BaseModel):
    """Aggregate volume counts of registered users, catalog tracks, blocked genres, and accesses."""

    model_config = ConfigDict(from_attributes=True)

    total_users: int
    total_tracks: int
    active_tracks: int
    blocked_genres: dict[str, int] = Field(default_factory=dict)
    total_accesses: int = 0
    accesses_by_track: list[TrackAccessRankResponse] = Field(default_factory=list)
    accesses_by_genre: list[GenreAccessCountResponse] = Field(default_factory=list)


class PlatformCostSettingsResponse(BaseModel):
    """Public representation of platform operational cost settings."""

    model_config = ConfigDict(from_attributes=True)

    content_cost_per_track: float
    infrastructure_fixed_cost: float
    infrastructure_cost_per_user: float
    updated_at: datetime | None = None


class UpdatePlatformCostsRequest(BaseModel):
    """Payload to update platform operational cost parameters."""

    model_config = ConfigDict(extra="forbid")

    content_cost_per_track: float = Field(ge=0.0)
    infrastructure_fixed_cost: float = Field(ge=0.0)
    infrastructure_cost_per_user: float = Field(ge=0.0)


class UserPlanSummaryResponse(BaseModel):
    """Summary overview of a registered user and their assigned subscription plan."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int | None = None
    email: str
    display_name: str
    age: int | None = None
    plan_name: str
    is_admin: bool


class UpdateAdminRoleRequest(BaseModel):
    """Payload to alter a user's administrator privilege status."""

    is_admin: bool


class CompactCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    new_version: int
    message: str


class SyncCatalogVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    synced: bool
    version: int
    message: str


class UpdateTrackGenreRequest(BaseModel):
    genre: str = Field(min_length=1)


class TrackGenreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    genre: str


class RegisterAdminRequest(BaseModel):
    """Payload to register a new administrator."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=2, max_length=50)
    age: int = Field(default=30, ge=18)
    birth_date: str | None = None


class AdminTrackAccessEntryResponse(BaseModel):
    """Admin-facing track access log entry preserving soft-deleted track state."""

    model_config = ConfigDict(from_attributes=True)

    access_id: int
    user_id: int
    user_display_name: str
    user_email: str
    track_id: int
    track_title: str
    track_artist: str
    track_genre: str
    track_is_deleted: bool
    source: str
    accessed_at: datetime


__all__ = [
    "AdminTrackAccessEntryResponse",
    "AudienceReportResponse",
    "BlockTrackRequest",
    "CompactCatalogResponse",
    "ExecutiveDashboardResponse",
    "GenreAccessCountResponse",
    "PlanResponse",
    "PlatformCostSettingsResponse",
    "RegisterAdminRequest",
    "SyncCatalogVersionResponse",
    "TrackAccessRankResponse",
    "TrackBlockResponse",
    "TrackExplicitResponse",
    "TrackGenreResponse",
    "UpdateAdminRoleRequest",
    "UpdatePlanAdminRequest",
    "UpdatePlatformCostsRequest",
    "UpdateTrackExplicitRequest",
    "UpdateTrackGenreRequest",
    "UserPlanSummaryResponse",
]
