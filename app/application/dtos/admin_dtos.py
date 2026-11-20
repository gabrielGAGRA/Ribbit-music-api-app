"""Data transfer objects for administrative actions and projections."""

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True, kw_only=True)
class UpdateSubscriptionPlanCommand:
    plan_id: int
    new_price: float | None = None
    new_name: str | None = None
    max_profiles: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class UpdateAdminRoleCommand:
    admin_id: int
    target_user_id: int
    is_admin: bool


@dataclass(slots=True, frozen=True, kw_only=True)
class UserPlanSummaryResult:
    user_id: int | None
    email: str
    display_name: str
    age: int | None = None
    plan_name: str
    is_admin: bool


@dataclass(slots=True, frozen=True, kw_only=True)
class ExecutiveDashboardResult:
    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int]
    revenue_by_plan: dict[str, float]


@dataclass(slots=True, frozen=True, kw_only=True)
class AudienceReportResult:
    total_users: int
    total_tracks: int
    active_tracks: int
    blocked_genres: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True, frozen=True, kw_only=True)
class AuditLogEntryResult:
    event: str
    status: str


@dataclass(slots=True, frozen=True, kw_only=True)
class RegisterAdministratorCommand:
    creator_admin_id: int
    email: str
    password: str
    display_name: str
    age: int = 30
    birth_date: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class CreateTrackCommand:
    title: str
    artist: str
    genre: str
    duration_seconds: int
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    spotify_id: str | None = None
    explicit: bool = False


@dataclass(slots=True, frozen=True, kw_only=True)
class AdminCatalogTrackResult:
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


__all__ = [
    "AdminCatalogTrackResult",
    "AudienceReportResult",
    "AuditLogEntryResult",
    "CreateTrackCommand",
    "ExecutiveDashboardResult",
    "RegisterAdministratorCommand",
    "UpdateAdminRoleCommand",
    "UpdateSubscriptionPlanCommand",
    "UserPlanSummaryResult",
]
