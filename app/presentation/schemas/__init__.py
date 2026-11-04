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
    GoogleLoginRequest,
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
    LinkSpotifyRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.presentation.schemas.spotify import (
    SpotifyAuthorizeUrlResponse,
    SpotifyConnectCallbackRequest,
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
    "DeckPlaylistRequest",
    "ExecutiveDashboardResponse",
    "GoogleLoginRequest",
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
    "SpotifyAuthorizeUrlResponse",
    "SpotifyConnectCallbackRequest",
    "SwipeAddTrackRequest",
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
