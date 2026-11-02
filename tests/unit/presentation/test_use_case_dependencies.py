"""Unit tests for presentation dependency provider utilities and container resolution."""

from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.application.ports.services import TokenServicePort, TrackPreviewPort
from app.application.use_cases.admin import (
    BlockTrackUseCase,
    GetAudienceReportUseCase,
    GetAuditLogsUseCase,
    GetExecutiveDashboardUseCase,
    GetTopModerationReviewsUseCase,
    ListAdministratorsUseCase,
    ListBlockedTracksUseCase,
    ListUsersWithPlansUseCase,
    PromoteUserToAdminUseCase,
    UpdateAdminRoleUseCase,
    UpdateSubscriptionPlanUseCase,
    UpdateTrackExplicitFlagUseCase,
)
from app.application.use_cases.auth import (
    AuthenticateAdminUseCase,
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from app.application.use_cases.discovery import (
    GetNextDiscoveryTrackUseCase,
    RecordSwipeInteractionUseCase,
)
from app.application.use_cases.jam import (
    AdvanceJamPlaybackUseCase,
    CloseJamUseCase,
    CreateJamUseCase,
    GetJamDeckUseCase,
    GetJamStateUseCase,
    JoinJamUseCase,
    SaveQueueTrackUseCase,
    VoteJamTrackUseCase,
    VoteSkipJamTrackUseCase,
)
from app.application.use_cases.playlist import (
    AddTrackToPlaylistUseCase,
    CreateDeckPlaylistUseCase,
    DeletePlaylistUseCase,
    ExportPlaylistToSpotifyUseCase,
    GetPlaylistDeckUseCase,
    ListUserPlaylistsUseCase,
    RemoveTrackFromPlaylistUseCase,
)
from app.application.use_cases.review import (
    DeleteReviewUseCase,
    GetCommunityFeedUseCase,
    GetRecentlyInteractedTracksUseCase,
    GetTrackReviewsUseCase,
    LikeReviewCommentUseCase,
    PublishReviewUseCase,
    SaveSearchTrackLikeUseCase,
    SearchTracksUseCase,
)
from app.application.use_cases.user import (
    AddFamilyMemberUseCase,
    CancelSubscriptionPlanUseCase,
    ChangeSubscriptionPlanUseCase,
    ChangeTrackInteractionUseCase,
    DeleteUserAccountUseCase,
    GetAnnualListeningStatsUseCase,
    GetUserProfileUseCase,
    LinkSpotifyAccountUseCase,
    ListBlockedGenresUseCase,
    ListFamilyMembersUseCase,
    ListPlansUseCase,
    ListUserInteractionsUseCase,
    RemoveFamilyMemberUseCase,
    UpdateBlockedGenresUseCase,
    UpdateProfileUseCase,
)
from app.composition import Container, build_container
from app.config import Settings
from app.infrastructure.repositories import create_connection
from app.presentation.dependencies.container import get_container, provide

ALL_USE_CASES = [
    RegisterUserUseCase,
    AuthenticateUserUseCase,
    AuthenticateAdminUseCase,
    GetNextDiscoveryTrackUseCase,
    RecordSwipeInteractionUseCase,
    CreateDeckPlaylistUseCase,
    GetPlaylistDeckUseCase,
    AddTrackToPlaylistUseCase,
    RemoveTrackFromPlaylistUseCase,
    DeletePlaylistUseCase,
    ExportPlaylistToSpotifyUseCase,
    ListUserPlaylistsUseCase,
    CreateJamUseCase,
    JoinJamUseCase,
    GetJamDeckUseCase,
    GetJamStateUseCase,
    VoteJamTrackUseCase,
    VoteSkipJamTrackUseCase,
    AdvanceJamPlaybackUseCase,
    SaveQueueTrackUseCase,
    CloseJamUseCase,
    SearchTracksUseCase,
    PublishReviewUseCase,
    DeleteReviewUseCase,
    GetTrackReviewsUseCase,
    GetCommunityFeedUseCase,
    LikeReviewCommentUseCase,
    GetRecentlyInteractedTracksUseCase,
    SaveSearchTrackLikeUseCase,
    GetUserProfileUseCase,
    UpdateProfileUseCase,
    DeleteUserAccountUseCase,
    ListPlansUseCase,
    ChangeSubscriptionPlanUseCase,
    CancelSubscriptionPlanUseCase,
    AddFamilyMemberUseCase,
    RemoveFamilyMemberUseCase,
    ListFamilyMembersUseCase,
    ListBlockedGenresUseCase,
    UpdateBlockedGenresUseCase,
    ListUserInteractionsUseCase,
    ChangeTrackInteractionUseCase,
    GetAnnualListeningStatsUseCase,
    LinkSpotifyAccountUseCase,
    GetExecutiveDashboardUseCase,
    ListUsersWithPlansUseCase,
    ListAdministratorsUseCase,
    UpdateAdminRoleUseCase,
    UpdateSubscriptionPlanUseCase,
    UpdateTrackExplicitFlagUseCase,
    BlockTrackUseCase,
    ListBlockedTracksUseCase,
    GetTopModerationReviewsUseCase,
    GetAudienceReportUseCase,
    GetAuditLogsUseCase,
    PromoteUserToAdminUseCase,
]


@pytest.fixture(scope="module")
def container() -> Container:
    conn = create_connection(":memory:")
    settings = Settings(database_path=":memory:", password_hash_iterations=1_000)
    return build_container(settings=settings, connection=conn)


@pytest.mark.parametrize("use_case_type", ALL_USE_CASES)
def test_container_resolves_every_use_case_by_type(
    container: Container, use_case_type: type
) -> None:
    resolved = container.resolve(use_case_type)
    assert isinstance(resolved, use_case_type)


def test_container_resolve_raises_key_error_for_unknown_type(
    container: Container,
) -> None:
    class UnknownService:
        pass

    with pytest.raises(KeyError, match="No component registered"):
        container.resolve(UnknownService)


def test_get_container_retrieves_container_from_app_state() -> None:
    request = MagicMock(spec=Request)
    mock_container = MagicMock(spec=Container)
    request.app.state.container = mock_container

    assert get_container(request) is mock_container


def test_provide_returns_dependency_calling_resolve() -> None:
    request = MagicMock(spec=Request)
    mock_container = MagicMock(spec=Container)
    dummy_instance = object()
    mock_container.resolve.return_value = dummy_instance
    request.app.state.container = mock_container

    dep_fn = provide(RegisterUserUseCase)
    result = dep_fn(request)

    assert result is dummy_instance
    mock_container.resolve.assert_called_once_with(RegisterUserUseCase)


def test_container_resolves_service_ports(container: Container) -> None:
    token_service = container.resolve(TokenServicePort)
    assert isinstance(token_service, TokenServicePort)

    preview_service = container.resolve(TrackPreviewPort)
    assert isinstance(preview_service, TrackPreviewPort)
