"""Application Data Transfer Objects (DTOs) for inbound commands and read projections."""

from app.application.dtos.admin_dtos import (
    AudienceReportResult,
    AuditLogEntryResult,
    ExecutiveDashboardResult,
    RegisterAdministratorCommand,
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
    ArtistStat,
    GenreStat,
    MonthlyInteractionStat,
    ReleaseYearStat,
    SourceStat,
    UpdateProfileCommand,
    UserProfileResult,
    YearlyInteractionStat,
)

__all__ = [
    "AddTrackToPlaylistCommand",
    "AnnualStatsResult",
    "ArtistStat",
    "AudienceReportResult",
    "AuditLogEntryResult",
    "AuthenticateAdminCommand",
    "AuthenticateUserCommand",
    "CreateDeckPlaylistCommand",
    "CreateJamCommand",
    "ExecutiveDashboardResult",
    "GenreStat",
    "JamStateResult",
    "MonthlyInteractionStat",
    "PlaylistWithTracksResult",
    "PublishReviewCommand",
    "RecordSwipeCommand",
    "RegisterAdministratorCommand",
    "RegisterUserCommand",
    "ReleaseYearStat",
    "SearchTracksCommand",
    "SourceStat",
    "UpdateProfileCommand",
    "UpdateSubscriptionPlanCommand",
    "UserPlanSummaryResult",
    "UserProfileResult",
    "VoteJamTrackCommand",
    "VoteSkipJamTrackCommand",
    "YearlyInteractionStat",
]
