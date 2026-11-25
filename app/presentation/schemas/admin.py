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


class FirestoreQuotaSummaryResponse(BaseModel):
    """Firestore usage vs free-tier quotas and projected monthly USD cost."""

    model_config = ConfigDict(from_attributes=True)

    reads_today: int = 0
    reads_free_limit: int = 50_000
    reads_percent: float = 0.0
    reads_rate_per_100k: float = 0.06
    writes_today: int = 0
    writes_free_limit: int = 20_000
    writes_percent: float = 0.0
    writes_rate_per_100k: float = 0.18
    deletes_today: int = 0
    deletes_free_limit: int = 20_000
    deletes_percent: float = 0.0
    deletes_rate_per_100k: float = 0.02
    stored_bytes: int = 0
    stored_gib: float = 0.0
    stored_free_limit_gib: float = 1.0
    stored_percent: float = 0.0
    egress_bytes_month: int = 0
    egress_gib_month: float = 0.0
    egress_free_limit_gib: float = 10.0
    egress_percent: float = 0.0
    monthly_estimated_cost: float = 0.0


class ExecutiveDashboardResponse(BaseModel):
    """Aggregated platform performance and subscription revenue metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int] = Field(default_factory=dict)
    revenue_by_plan: dict[str, float] = Field(default_factory=dict)
    profit_by_plan: dict[str, float] = Field(default_factory=dict)
    paid_plans_revenue: float = 0.0
    paid_plans_profit: float = 0.0
    cost_to_revenue_percent: float = 0.0
    gross_revenue: float = 0.0
    content_cost: float = 0.0
    infrastructure_cost: float = 0.0
    total_costs: float = 0.0
    active_tracks_count: int = 0
    content_cost_per_track: float = 0.0
    infrastructure_fixed_cost: float = 0.0
    infrastructure_cost_per_user: float = 0.0
    firestore_usage: FirestoreQuotaSummaryResponse | None = None


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


class CreateTrackAdminRequest(BaseModel):
    """Payload to register a new catalog track from the admin console."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    duration_seconds: int = Field(gt=0)
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    spotify_id: str | None = None
    explicit: bool = False


class AdminCatalogTrackResponse(BaseModel):
    """Admin representation of a catalog track enriched with interaction and review metrics."""

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
    likes_count: int = 0
    dislikes_count: int = 0
    superlikes_count: int = 0
    average_rating: float | None = None
    review_count: int = 0


class ExternalTrackCandidateResponse(BaseModel):
    """External track search candidate ready to be added to the Delta Table."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    artist: str
    duration_seconds: int = 180
    genre: str = "Unknown"
    spotify_id: str | None = None
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    explicit: bool = False
    already_in_catalog: bool = False


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
    "AdminCatalogTrackResponse",
    "AdminTrackAccessEntryResponse",
    "AudienceReportResponse",
    "BlockTrackRequest",
    "CompactCatalogResponse",
    "CreateTrackAdminRequest",
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
