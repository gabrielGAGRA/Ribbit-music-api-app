"""Unit tests for admin console router functions."""

from unittest.mock import MagicMock

from fastapi import Request

from app.application.dtos import (
    AuthenticateAdminCommand,
    UpdateSubscriptionPlanCommand,
)
from app.application.use_cases.admin import (
    BlockTrackUseCase,
    GetAudienceReportUseCase,
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
from app.application.use_cases.auth import AuthenticateAdminUseCase
from app.domain.models import Plan, ReviewComment, Track, User
from app.presentation.routers.admin import (
    block_track,
    get_audience_report,
    get_executive_dashboard,
    get_top_moderation_reviews,
    list_administrators,
    list_blocked_tracks,
    list_plans,
    list_users,
    login_admin,
    promote_user_to_admin,
    update_admin_role,
    update_plan,
    update_track_explicit,
)
from app.presentation.schemas.admin import (
    BlockTrackRequest,
    UpdateAdminRoleRequest,
    UpdatePlanAdminRequest,
    UpdateTrackExplicitRequest,
)
from app.presentation.schemas.auth import LoginRequest


def test_login_admin_forwards_command_and_returns_admin_user() -> None:
    mock_use_case = MagicMock(spec=AuthenticateAdminUseCase)
    admin = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="hashed_pw",
        display_name="Chief Toad",
        age=35,
        plan_id=2,
        is_admin=True,
    )
    mock_use_case.execute.return_value = admin
    req = LoginRequest(email="admin@ribbit.com", password="adminpassword")

    res = login_admin(req=req, use_case=mock_use_case)

    assert res.user_id == 1
    assert res.is_admin is True
    mock_use_case.execute.assert_called_once_with(
        AuthenticateAdminCommand(
            email="admin@ribbit.com",
            password="adminpassword",
        )
    )


def test_get_executive_dashboard_returns_aggregated_metrics() -> None:
    mock_use_case = MagicMock(spec=GetExecutiveDashboardUseCase)
    mock_use_case.execute.return_value = {
        "total_users": 50,
        "estimated_net_revenue": 499.50,
        "users_by_plan": {"Free": 25, "Premium": 25},
        "revenue_by_plan": {"Free": 0.0, "Premium": 499.50},
    }

    res = get_executive_dashboard(use_case=mock_use_case)

    assert res.total_users == 50
    assert res.estimated_net_revenue == 499.50
    assert res.users_by_plan == {"Free": 25, "Premium": 25}
    assert res.revenue_by_plan == {"Free": 0.0, "Premium": 499.50}
    mock_use_case.execute.assert_called_once_with()


def test_list_users_returns_user_plan_summaries() -> None:
    mock_use_case = MagicMock(spec=ListUsersWithPlansUseCase)
    mock_use_case.execute.return_value = [
        {
            "user_id": 10,
            "email": "user@ribbit.com",
            "display_name": "Listener",
            "age": 20,
            "plan_name": "Premium",
            "is_admin": False,
        }
    ]

    res = list_users(use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].user_id == 10
    assert res[0].plan_name == "Premium"
    assert res[0].is_admin is False
    mock_use_case.execute.assert_called_once_with()


def test_get_audience_report_returns_counts() -> None:
    mock_use_case = MagicMock(spec=GetAudienceReportUseCase)
    mock_use_case.execute.return_value = {
        "total_users": 100,
        "total_tracks": 500,
        "active_tracks": 480,
    }

    res = get_audience_report(use_case=mock_use_case)

    assert res.total_users == 100
    assert res.total_tracks == 500
    assert res.active_tracks == 480
    mock_use_case.execute.assert_called_once_with()


def test_list_administrators_router_returns_users() -> None:
    mock_use_case = MagicMock(spec=ListAdministratorsUseCase)
    admin = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="pw",
        display_name="Admin",
        age=32,
        plan_id=1,
        is_admin=True,
    )
    mock_use_case.execute.return_value = [admin]

    res = list_administrators(use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].user_id == 1
    assert res[0].is_admin is True
    mock_use_case.execute.assert_called_once_with()


def test_update_admin_role_router_updates_role() -> None:
    mock_use_case = MagicMock(spec=UpdateAdminRoleUseCase)
    target = User(
        user_id=2,
        email="mod@ribbit.com",
        password_hash="pw",
        display_name="Mod",
        age=25,
        plan_id=1,
        is_admin=True,
    )
    mock_use_case.execute.return_value = target
    req = UpdateAdminRoleRequest(is_admin=True)

    res = update_admin_role(user_id=2, req=req, admin_id=1, use_case=mock_use_case)

    assert res.user_id == 2
    assert res.is_admin is True
    mock_use_case.execute.assert_called_once_with(
        admin_id=1, target_user_id=2, is_admin=True
    )


def test_list_blocked_tracks_router_returns_tracks() -> None:
    mock_use_case = MagicMock(spec=ListBlockedTracksUseCase)
    track = Track(
        track_id=88,
        title="Blocked Track",
        artist="Artist",
        duration_seconds=180,
        genre="Metal",
        is_deleted=True,
    )
    mock_use_case.execute.return_value = [track]

    res = list_blocked_tracks(use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].track_id == 88
    assert res[0].is_deleted is True
    mock_use_case.execute.assert_called_once_with()


def test_block_track_forwards_track_id_and_returns_blocked_status() -> None:
    mock_use_case = MagicMock(spec=BlockTrackUseCase)
    mock_use_case.execute.return_value = True

    res = block_track(track_id=77, use_case=mock_use_case)

    assert res.blocked is True
    mock_use_case.execute.assert_called_once_with(track_id=77)


def test_block_track_with_request_body_unblocks_track() -> None:
    mock_use_case = MagicMock(spec=BlockTrackUseCase)
    mock_use_case.execute.return_value = False
    req = BlockTrackRequest(blocked=False)

    res = block_track(track_id=77, req=req, use_case=mock_use_case)

    assert res.blocked is False
    mock_use_case.execute.assert_called_once_with(track_id=77, blocked=False)


def test_list_plans_router_returns_plans_from_container() -> None:
    mock_plan = Plan(
        plan_id=1,
        name="Free",
        initial_monthly_price=0.0,
        initial_max_profiles=1,
    )
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.container.plan_repo.list_all.return_value = [mock_plan]

    res = list_plans(request=mock_request)

    assert len(res) == 1
    assert res[0].plan_id == 1
    assert res[0].name == "Free"


def test_update_track_explicit_forwards_flag_and_returns_response() -> None:
    mock_use_case = MagicMock(spec=UpdateTrackExplicitFlagUseCase)
    mock_use_case.execute.return_value = True
    req = UpdateTrackExplicitRequest(explicit=True)

    res = update_track_explicit(track_id=77, req=req, use_case=mock_use_case)

    assert res.track_id == 77
    assert res.explicit is True
    mock_use_case.execute.assert_called_once_with(track_id=77, explicit=True)


def test_promote_user_to_admin_returns_promoted_user() -> None:
    mock_use_case = MagicMock(spec=PromoteUserToAdminUseCase)
    promoted = User(
        user_id=15,
        email="mod@ribbit.com",
        password_hash="pw",
        display_name="New Mod",
        age=29,
        plan_id=1,
        is_admin=True,
    )
    mock_use_case.execute.return_value = promoted

    res = promote_user_to_admin(user_id=15, use_case=mock_use_case)

    assert res.user_id == 15
    assert res.is_admin is True
    mock_use_case.execute.assert_called_once_with(user_id=15)


def test_update_plan_forwards_command_and_returns_plan_response() -> None:
    mock_use_case = MagicMock(spec=UpdateSubscriptionPlanUseCase)
    plan = Plan(
        plan_id=3,
        name="Family Plus",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    mock_use_case.execute.return_value = plan
    req = UpdatePlanAdminRequest(
        new_price=34.90,
        new_name="Family Plus",
        max_profiles=6,
    )

    res = update_plan(plan_id=3, req=req, use_case=mock_use_case)

    assert res.plan_id == 3
    assert res.name == "Family Plus"
    assert res.monthly_price == 34.90
    assert res.max_profiles == 6
    mock_use_case.execute.assert_called_once_with(
        UpdateSubscriptionPlanCommand(
            plan_id=3,
            new_price=34.90,
            new_name="Family Plus",
            max_profiles=6,
        )
    )


def test_get_top_moderation_reviews_returns_mapped_reviews() -> None:
    mock_use_case = MagicMock(spec=GetTopModerationReviewsUseCase)
    review = ReviewComment(
        review_id=9,
        user_id=10,
        track_id=50,
        initial_rating=1,
        text="Controversial take",
        initial_likes_count=42,
    )
    mock_use_case.execute.return_value = [review]

    res = get_top_moderation_reviews(use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].review_id == 9
    assert res[0].likes_count == 42
    mock_use_case.execute.assert_called_once_with()
