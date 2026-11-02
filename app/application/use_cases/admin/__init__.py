"""Administrative use cases."""

from app.application.use_cases.admin.block_track import BlockTrackUseCase
from app.application.use_cases.admin.get_audience_report import (
    GetAudienceReportUseCase,
)
from app.application.use_cases.admin.get_audit_logs import GetAuditLogsUseCase
from app.application.use_cases.admin.get_executive_dashboard import (
    GetExecutiveDashboardUseCase,
)
from app.application.use_cases.admin.get_top_moderation_reviews import (
    GetTopModerationReviewsUseCase,
)
from app.application.use_cases.admin.list_administrators import (
    ListAdministratorsUseCase,
)
from app.application.use_cases.admin.list_blocked_tracks import (
    ListBlockedTracksUseCase,
)
from app.application.use_cases.admin.list_users_with_plans import (
    ListUsersWithPlansUseCase,
)
from app.application.use_cases.admin.promote_user_to_admin import (
    PromoteUserToAdminUseCase,
)
from app.application.use_cases.admin.update_admin_role import (
    UpdateAdminRoleUseCase,
)
from app.application.use_cases.admin.update_subscription_plan import (
    UpdateSubscriptionPlanUseCase,
)
from app.application.use_cases.admin.update_track_explicit_flag import (
    UpdateTrackExplicitFlagUseCase,
)

__all__ = [
    "BlockTrackUseCase",
    "GetAudienceReportUseCase",
    "GetAuditLogsUseCase",
    "GetExecutiveDashboardUseCase",
    "GetTopModerationReviewsUseCase",
    "ListAdministratorsUseCase",
    "ListBlockedTracksUseCase",
    "ListUsersWithPlansUseCase",
    "PromoteUserToAdminUseCase",
    "UpdateAdminRoleUseCase",
    "UpdateSubscriptionPlanUseCase",
    "UpdateTrackExplicitFlagUseCase",
]
