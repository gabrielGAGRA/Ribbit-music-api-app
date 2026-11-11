"""Presentation schemas package exposing all request and response models."""

from app.presentation.schemas.admin import (
    AudienceReportResponse,
    ExecutiveDashboardResponse,
    PlanResponse,
    TrackBlockResponse,
    TrackExplicitResponse,
    UpdatePlanAdminRequest,
    UpdateTrackExplicitRequest,
    UserPlanSummaryResponse,
)
from app.presentation.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterUserRequest,
    UserResponse,
)
from app.presentation.schemas.common import ActionSuccessResponse
from app.presentation.schemas.discovery import (
    ChangeInteractionRequest,
    InteractionRequest,
    InteractionResponse,
    TrackSearchQuery,
    UndoInteractionResponse,
)
from app.presentation.schemas.jams import (
    CreateJamRequest,
    JamQueueItemResponse,
    JamResponse,
    JamStateResponse,
    JoinJamRequest,
    SkipJamTrackRequest,
    VoteJamTrackRequest,
)
from app.presentation.schemas.playlists import (
    DeckPlaylistRequest,
    PlaylistResponse,
    SwipeAddTrackRequest,
    TrackResponse,
)
from app.presentation.schemas.profile import (
    AddFamilyMemberRequest,
    AnnualStatsResponse,
    BlockedGenresRequest,
    ChangePlanRequest,
    FavoriteGenresRequest,
    LinkSpotifyRequest,
    ThemePreferenceRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.presentation.schemas.tracks_reviews import (
    PublishReviewRequest,
    ReviewResponse,
)

__all__ = [
    "ActionSuccessResponse",
    "AddFamilyMemberRequest",
    "AnnualStatsResponse",
    "AudienceReportResponse",
    "AuthResponse",
    "BlockedGenresRequest",
    "ChangeInteractionRequest",
    "ChangePlanRequest",
    "CreateJamRequest",
    "FavoriteGenresRequest",
    "DeckPlaylistRequest",
    "ExecutiveDashboardResponse",
    "InteractionRequest",
    "InteractionResponse",
    "JamQueueItemResponse",
    "JamResponse",
    "JamStateResponse",
    "JoinJamRequest",
    "LinkSpotifyRequest",
    "LoginRequest",
    "PlanResponse",
    "PlaylistResponse",
    "PublishReviewRequest",
    "RegisterUserRequest",
    "ReviewResponse",
    "SkipJamTrackRequest",
    "SwipeAddTrackRequest",
    "ThemePreferenceRequest",
    "TrackBlockResponse",
    "TrackExplicitResponse",
    "TrackResponse",
    "TrackSearchQuery",
    "UndoInteractionResponse",
    "UpdatePlanAdminRequest",
    "UpdateProfileRequest",
    "UpdateTrackExplicitRequest",
    "UserProfileResponse",
    "UserPlanSummaryResponse",
    "UserResponse",
    "VoteJamTrackRequest",
]
