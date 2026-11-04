"""Administrative presentation schemas."""

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


class AudienceReportResponse(BaseModel):
    """Aggregate volume counts of registered users, catalog tracks, and blocked genres."""

    model_config = ConfigDict(from_attributes=True)

    total_users: int
    total_tracks: int
    active_tracks: int
    blocked_genres: dict[str, int] = Field(default_factory=dict)


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
    """Response returned upon consolidating micro-deltas into the main catalog."""

    model_config = ConfigDict(from_attributes=True)

    new_version: int
    message: str


class SyncCatalogVersionResponse(BaseModel):
    """Response returned upon checking and syncing local database against remote catalog version."""

    model_config = ConfigDict(from_attributes=True)

    synced: bool
    version: int
    message: str


class UpdateTrackGenreRequest(BaseModel):
    """Payload to alter a track genre."""

    genre: str


class TrackGenreResponse(BaseModel):
    """Response returned upon updating genre on a track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    genre: str


__all__ = [
    "AudienceReportResponse",
    "BlockTrackRequest",
    "CompactCatalogResponse",
    "ExecutiveDashboardResponse",
    "PlanResponse",
    "SyncCatalogVersionResponse",
    "TrackBlockResponse",
    "TrackExplicitResponse",
    "TrackGenreResponse",
    "UpdateAdminRoleRequest",
    "UpdatePlanAdminRequest",
    "UpdateTrackExplicitRequest",
    "UpdateTrackGenreRequest",
    "UserPlanSummaryResponse",
]
