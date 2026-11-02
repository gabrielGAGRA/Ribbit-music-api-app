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
    age: int
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


__all__ = [
    "AudienceReportResult",
    "AuditLogEntryResult",
    "ExecutiveDashboardResult",
    "UpdateAdminRoleCommand",
    "UpdateSubscriptionPlanCommand",
    "UserPlanSummaryResult",
]
