"""Application Data Transfer Objects (DTOs) for inbound commands and read projections."""

from app.application.dtos.admin_dtos import (
    AudienceReportResult,
    AuditLogEntryResult,
    ExecutiveDashboardResult,
    UpdateSubscriptionPlanCommand,
    UserPlanSummaryResult,
)
from app.application.dtos.auth_dtos import (
    AuthenticateAdminCommand,
    AuthenticateUserCommand,
    RegisterUserCommand,
)
from app.application.dtos.discovery_dtos import RecordSwipeCommand
from app.application.dtos.jam_dtos import (
    CreateJamCommand,
    JamStateResult,
    VoteJamTrackCommand,
    VoteSkipJamTrackCommand,
)
from app.application.dtos.playlist_dtos import (
    AddTrackToPlaylistCommand,
    CreateDeckPlaylistCommand,
    PlaylistWithTracksResult,
)
from app.application.dtos.review_dtos import (
    PublishReviewCommand,
    SearchTracksCommand,
)
from app.application.dtos.user_dtos import (
    AnnualStatsResult,
    UpdateProfileCommand,
    UserProfileResult,
)

__all__ = [
    "AddTrackToPlaylistCommand",
    "AnnualStatsResult",
    "AudienceReportResult",
    "AuditLogEntryResult",
    "AuthenticateAdminCommand",
    "AuthenticateUserCommand",
    "CreateDeckPlaylistCommand",
    "CreateJamCommand",
    "ExecutiveDashboardResult",
    "JamStateResult",
    "PlaylistWithTracksResult",
    "PublishReviewCommand",
    "RecordSwipeCommand",
    "RegisterUserCommand",
    "SearchTracksCommand",
    "UpdateProfileCommand",
    "UpdateSubscriptionPlanCommand",
    "UserPlanSummaryResult",
    "UserProfileResult",
    "VoteJamTrackCommand",
    "VoteSkipJamTrackCommand",
]
