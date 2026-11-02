"""Unit tests for profile, subscription plans, premium, and family router functions."""

from unittest.mock import MagicMock

from app.application.dtos import UpdateProfileCommand
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
from app.domain.models import Interaction, InteractionAction, Plan, User
from app.presentation.routers.profile import (
    add_family_member,
    cancel_plan,
    change_interaction,
    change_plan,
    delete_account,
    get_annual_stats,
    get_profile,
    link_spotify,
    list_blocked_genres,
    list_family_members,
    list_history,
    list_plans,
    remove_family_member,
    update_blocked_genres,
    update_profile,
)
from app.presentation.schemas import (
    AddFamilyMemberRequest,
    BlockedGenresRequest,
    ChangeInteractionRequest,
    ChangePlanRequest,
    LinkSpotifyRequest,
    UpdateProfileRequest,
)


def _sample_user(user_id: int = 10, plan_id: int = 2) -> User:
    return User(
        user_id=user_id,
        email=f"user{user_id}@ribbit.com",
        password_hash="hashed_pw",
        display_name=f"User {user_id}",
        age=24,
        plan_id=plan_id,
    )


def _sample_plan(plan_id: int = 2) -> Plan:
    return Plan(
        plan_id=plan_id,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )


def test_get_profile_returns_composite_user_and_plan() -> None:
    mock_use_case = MagicMock(spec=GetUserProfileUseCase)
    mock_use_case.execute.return_value = {
        "user": _sample_user(10, 2),
        "plan": _sample_plan(2),
    }

    res = get_profile(user_id=10, use_case=mock_use_case)

    assert res.user.user_id == 10
    assert res.plan.plan_id == 2
    assert res.plan.name == "Premium"
    mock_use_case.execute.assert_called_once_with(user_id=10)


def test_update_profile_forwards_command_and_returns_user() -> None:
    mock_use_case = MagicMock(spec=UpdateProfileUseCase)
    updated_user = _sample_user(10)
    updated_user.update_profile(display_name="Updated Frog")
    mock_use_case.execute.return_value = updated_user
    req = UpdateProfileRequest(
        display_name="Updated Frog",
        new_password="newpassword123",
        current_password="oldpassword123",
    )

    res = update_profile(req=req, user_id=10, use_case=mock_use_case)

    assert res.user_id == 10
    assert res.display_name == "Updated Frog"
    mock_use_case.execute.assert_called_once_with(
        UpdateProfileCommand(
            user_id=10,
            display_name="Updated Frog",
            new_password="newpassword123",
            current_password="oldpassword123",
        )
    )


def test_link_spotify_forwards_parameters_and_returns_user() -> None:
    mock_use_case = MagicMock(spec=LinkSpotifyAccountUseCase)
    user = _sample_user(10)
    user.link_spotify("spotify_user_abc")
    mock_use_case.execute.return_value = user
    req = LinkSpotifyRequest(user_id=10, spotify_id="spotify_user_abc")

    res = link_spotify(req=req, use_case=mock_use_case)

    assert res.user_id == 10
    assert res.spotify_id == "spotify_user_abc"
    mock_use_case.execute.assert_called_once_with(
        user_id=10,
        spotify_id="spotify_user_abc",
    )


def test_list_plans_returns_all_mapped_plans() -> None:
    mock_use_case = MagicMock(spec=ListPlansUseCase)
    mock_use_case.execute.return_value = [_sample_plan(2)]

    res = list_plans(use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].plan_id == 2
    assert res[0].monthly_price == 19.90
    mock_use_case.execute.assert_called_once_with()


def test_change_plan_forwards_ids_and_returns_updated_user() -> None:
    mock_use_case = MagicMock(spec=ChangeSubscriptionPlanUseCase)
    user = _sample_user(10, plan_id=3)
    mock_use_case.execute.return_value = user
    req = ChangePlanRequest(user_id=10, new_plan_id=3)

    res = change_plan(req=req, use_case=mock_use_case)

    assert res.user_id == 10
    assert res.plan_id == 3
    mock_use_case.execute.assert_called_once_with(user_id=10, new_plan_id=3)


def test_cancel_plan_forwards_user_id_and_returns_user() -> None:
    mock_use_case = MagicMock(spec=CancelSubscriptionPlanUseCase)
    user = _sample_user(10, plan_id=1)
    mock_use_case.execute.return_value = user

    res = cancel_plan(user_id=10, use_case=mock_use_case)

    assert res.user_id == 10
    assert res.plan_id == 1
    mock_use_case.execute.assert_called_once_with(user_id=10)


def test_delete_account_forwards_user_id_and_returns_success() -> None:
    mock_use_case = MagicMock(spec=DeleteUserAccountUseCase)
    mock_use_case.execute.return_value = True

    res = delete_account(user_id=10, use_case=mock_use_case)

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(user_id=10)


def test_get_annual_stats_returns_mapped_stats_response() -> None:
    mock_use_case = MagicMock(spec=GetAnnualListeningStatsUseCase)
    mock_use_case.execute.return_value = {
        "user_id": 10,
        "estimated_listening_hours": 42.5,
        "total_likes": 120,
        "top_genres": ["indie", "rock"],
        "top_artists": ["Frog Band"],
    }

    res = get_annual_stats(user_id=10, use_case=mock_use_case)

    assert res.user_id == 10
    assert res.estimated_listening_hours == 42.5
    assert res.total_likes == 120
    assert res.top_genres == ["indie", "rock"]
    assert res.top_artists == ["Frog Band"]
    mock_use_case.execute.assert_called_once_with(user_id=10)


def test_change_interaction_converts_action_and_returns_interaction() -> None:
    mock_use_case = MagicMock(spec=ChangeTrackInteractionUseCase)
    interaction = Interaction(
        interaction_id=8,
        user_id=10,
        track_id=55,
        action=InteractionAction.LIKE,
    )
    mock_use_case.execute.return_value = interaction
    req = ChangeInteractionRequest(user_id=10, track_id=55, new_action="like")

    res = change_interaction(req=req, use_case=mock_use_case)

    assert res.interaction_id == 8
    assert res.action == "like"
    mock_use_case.execute.assert_called_once_with(
        user_id=10,
        track_id=55,
        new_action=InteractionAction.LIKE,
    )


def test_list_history_without_category_passes_none_action() -> None:
    mock_use_case = MagicMock(spec=ListUserInteractionsUseCase)
    interaction = Interaction(
        interaction_id=8,
        user_id=10,
        track_id=55,
        action=InteractionAction.DISLIKE,
    )
    mock_use_case.execute.return_value = [interaction]

    res = list_history(user_id=10, use_case=mock_use_case, category=None)

    assert len(res) == 1
    assert res[0].action == "dislike"
    mock_use_case.execute.assert_called_once_with(user_id=10, action=None)


def test_list_history_with_category_converts_to_interaction_action() -> None:
    mock_use_case = MagicMock(spec=ListUserInteractionsUseCase)
    mock_use_case.execute.return_value = []

    res = list_history(user_id=10, use_case=mock_use_case, category="SUPERLIKE")

    assert res == []
    mock_use_case.execute.assert_called_once_with(
        user_id=10,
        action=InteractionAction.SUPERLIKE,
    )


def test_list_blocked_genres_returns_genre_strings() -> None:
    mock_use_case = MagicMock(spec=ListBlockedGenresUseCase)
    mock_use_case.execute.return_value = ["funk", "country"]

    res = list_blocked_genres(user_id=10, use_case=mock_use_case)

    assert res == ["funk", "country"]
    mock_use_case.execute.assert_called_once_with(user_id=10)


def test_update_blocked_genres_parses_comma_separated_string() -> None:
    mock_use_case = MagicMock(spec=UpdateBlockedGenresUseCase)
    user = _sample_user(10)
    user.update_blocked_genres(["rock", "pop"])
    mock_use_case.execute.return_value = user
    req = BlockedGenresRequest(user_id=10, blocked_genres=" rock , pop ,  ")

    res = update_blocked_genres(req=req, use_case=mock_use_case)

    assert res.user_id == 10
    mock_use_case.execute.assert_called_once_with(
        user_id=10,
        blocked_genres=["rock", "pop"],
    )


def test_update_blocked_genres_accepts_list_of_strings() -> None:
    mock_use_case = MagicMock(spec=UpdateBlockedGenresUseCase)
    user = _sample_user(10)
    user.update_blocked_genres(["jazz", "metal"])
    mock_use_case.execute.return_value = user
    req = BlockedGenresRequest(user_id=10, blocked_genres=[" jazz ", "metal", " "])

    res = update_blocked_genres(req=req, use_case=mock_use_case)

    assert res.user_id == 10
    mock_use_case.execute.assert_called_once_with(
        user_id=10,
        blocked_genres=["jazz", "metal"],
    )


def test_list_family_members_returns_dependent_users() -> None:
    mock_use_case = MagicMock(spec=ListFamilyMembersUseCase)
    dependent = _sample_user(11, plan_id=3)
    dependent.link_primary_account(10)
    mock_use_case.execute.return_value = [dependent]

    res = list_family_members(primary_account_id=10, use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].user_id == 11
    assert res[0].primary_account_id == 10
    mock_use_case.execute.assert_called_once_with(primary_user_id=10)


def test_add_family_member_forwards_ids_and_returns_dependent() -> None:
    mock_use_case = MagicMock(spec=AddFamilyMemberUseCase)
    dependent = _sample_user(12, plan_id=3)
    dependent.link_primary_account(10)
    mock_use_case.execute.return_value = dependent
    req = AddFamilyMemberRequest(primary_account_id=10, dependent_user_id=12)

    res = add_family_member(req=req, use_case=mock_use_case)

    assert res.user_id == 12
    assert res.primary_account_id == 10
    mock_use_case.execute.assert_called_once_with(
        primary_user_id=10,
        dependent_user_id=12,
    )


def test_remove_family_member_forwards_ids_and_returns_unlinked_user() -> None:
    mock_use_case = MagicMock(spec=RemoveFamilyMemberUseCase)
    unlinked = _sample_user(12, plan_id=1)
    mock_use_case.execute.return_value = unlinked

    res = remove_family_member(
        member_id=12,
        primary_account_id=10,
        use_case=mock_use_case,
    )

    assert res.user_id == 12
    assert res.primary_account_id is None
    mock_use_case.execute.assert_called_once_with(
        primary_user_id=10,
        member_user_id=12,
    )


def test_add_family_member_provisioning_flow_forwards_credentials() -> None:
    mock_use_case = MagicMock(spec=AddFamilyMemberUseCase)
    created_dep = User(
        user_id=15,
        email="kid@ribbit.com",
        password_hash="hashed_pw",
        display_name="Little Frog",
        age=12,
        plan_id=3,
        primary_account_id=10,
        birth_date="2014-05-10",
    )
    mock_use_case.execute.return_value = created_dep
    req = AddFamilyMemberRequest(
        email="kid@ribbit.com",
        password="kidpassword",
        display_name="Little Frog",
        birth_date="2014-05-10",
    )

    res = add_family_member(req=req, use_case=mock_use_case, auth_user_id=10)

    assert res.user_id == 15
    assert res.email == "kid@ribbit.com"
    assert res.primary_account_id == 10
    mock_use_case.execute.assert_called_once_with(
        primary_user_id=10,
        email="kid@ribbit.com",
        password="kidpassword",
        display_name="Little Frog",
        birth_date="2014-05-10",
    )


def test_get_profile_includes_recent_interactions() -> None:
    mock_use_case = MagicMock(spec=GetUserProfileUseCase)
    user = _sample_user(10, 2)
    plan = _sample_plan(2)
    interaction = Interaction(
        interaction_id=1,
        user_id=10,
        track_id=5,
        action=InteractionAction.LIKE,
    )
    mock_use_case.execute.return_value = {
        "user": user,
        "plan": plan,
        "recent_interactions": [interaction],
    }

    res = get_profile(user_id=10, use_case=mock_use_case)

    assert res.user.user_id == 10
    assert len(res.recent_interactions) == 1
    assert res.recent_interactions[0].track_id == 5
    assert res.recent_interactions[0].action == "like"
    assert len(res.interacoes_recentes) == 1


def test_profile_router_has_portuguese_route_aliases() -> None:
    from app.presentation.routers.profile import router

    paths = [route.path for route in router.routes]  # type: ignore[attr-defined]
    assert "/api/profile/me" in paths
    assert "/api/perfil/me" in paths
    assert "/api/plans" in paths
    assert "/api/planos" in paths
    assert "/api/profile/plan" in paths
    assert "/api/perfil/plano" in paths
    assert "/api/profile/account" in paths
    assert "/api/perfil/conta" in paths
    assert "/api/profile/blocked-genres" in paths
    assert "/api/perfil/generos-bloqueados" in paths
    assert "/api/profile/family/members" in paths
    assert "/api/perfil/familia/membros" in paths
    assert "/api/profile/family/members/{member_id}" in paths
    assert "/api/perfil/familia/membros/{member_id}" in paths
