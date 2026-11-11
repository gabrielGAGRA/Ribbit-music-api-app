"""Unit tests for Pydantic presentation schemas and validation boundaries."""

from typing import Literal

import pytest
from pydantic import ValidationError

from app.presentation.schemas import (
    ActionSuccessResponse,
    ChangeInteractionRequest,
    CreateJamRequest,
    DeckPlaylistRequest,
    ExecutiveDashboardResponse,
    InteractionRequest,
    JoinJamRequest,
    PublishReviewRequest,
    RegisterUserRequest,
    TrackSearchQuery,
    UpdateProfileRequest,
    VoteJamTrackRequest,
)


def test_register_user_request_valid_payload() -> None:
    req = RegisterUserRequest(
        email="frog@ribbit.com",
        password="secretpassword",
        display_name="Ribbit User",
        age=18,
    )
    assert req.email == "frog@ribbit.com"
    assert req.plan_id is None


@pytest.mark.parametrize(
    ("password", "display_name", "age"),
    [
        ("12345", "Valid Name", 20),
        ("validpass", "A", 20),
        ("validpass", "X" * 51, 20),
        ("validpass", "Valid Name", -1),
    ],
)
def test_register_user_request_rejects_invalid_fields(
    password: str,
    display_name: str,
    age: int,
) -> None:
    with pytest.raises(ValidationError):
        RegisterUserRequest(
            email="frog@ribbit.com",
            password=password,
            display_name=display_name,
            age=age,
        )


@pytest.mark.parametrize("action", ["like", "superlike", "dislike"])
def test_interaction_request_accepts_only_valid_literals(
    action: Literal["like", "superlike", "dislike"],
) -> None:
    req = InteractionRequest(track_id=2, action=action)
    assert req.action == action


def test_interaction_request_rejects_invalid_action() -> None:
    with pytest.raises(ValidationError):
        InteractionRequest.model_validate({"track_id": 2, "action": "love"})


def test_change_interaction_request_rejects_invalid_action() -> None:
    with pytest.raises(ValidationError):
        ChangeInteractionRequest.model_validate({"track_id": 2, "new_action": "skip"})


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (101, 0),
        (20, -1),
    ],
)
def test_track_search_query_enforces_pagination_bounds(limit: int, offset: int) -> None:
    with pytest.raises(ValidationError):
        TrackSearchQuery(limit=limit, offset=offset)


def test_create_jam_request_enforces_room_name_length() -> None:
    with pytest.raises(ValidationError):
        CreateJamRequest(room_name="")

    with pytest.raises(ValidationError):
        CreateJamRequest(room_name="R" * 101)


def test_join_jam_request_enforces_room_code_length() -> None:
    with pytest.raises(ValidationError):
        JoinJamRequest(room_code="")

    with pytest.raises(ValidationError):
        JoinJamRequest(room_code="C" * 21)


@pytest.mark.parametrize("points", [0, -1, 11])
def test_vote_jam_track_request_enforces_points_bounds(points: int) -> None:
    with pytest.raises(ValidationError):
        VoteJamTrackRequest(track_id=10, points=points)


@pytest.mark.parametrize(
    ("name", "duration_minutes", "year", "description"),
    [
        ("", 30, 2020, "ok"),
        ("X" * 101, 30, 2020, "ok"),
        ("Valid", 0, 2020, "ok"),
        ("Valid", 601, 2020, "ok"),
        ("Valid", 30, 2020, "D" * 501),
    ],
)
def test_deck_playlist_request_enforces_field_constraints(
    name: str,
    duration_minutes: int | None,
    year: int | None,
    description: str | None,
) -> None:
    with pytest.raises(ValidationError):
        DeckPlaylistRequest(
            name=name,
            duration_minutes=duration_minutes,
            year=year,
            description=description,
        )


@pytest.mark.parametrize("year", [1899, 2101])
def test_deck_playlist_request_accepts_any_integer_year(year: int) -> None:
    request = DeckPlaylistRequest(name="Valid", duration_minutes=30, year=year)

    assert request.year == year


@pytest.mark.parametrize(
    ("display_name", "new_password"),
    [
        ("A", None),
        ("N" * 51, None),
        (None, "12345"),
    ],
)
def test_update_profile_request_enforces_min_and_max_lengths(
    display_name: str | None,
    new_password: str | None,
) -> None:
    with pytest.raises(ValidationError):
        UpdateProfileRequest(
            display_name=display_name,
            new_password=new_password,
        )


@pytest.mark.parametrize(
    ("rating", "text"),
    [
        (0, "Too low"),
        (6, "Too high"),
        (5, "T" * 1001),
    ],
)
def test_publish_review_request_enforces_rating_and_text_bounds(
    rating: int,
    text: str | None,
) -> None:
    with pytest.raises(ValidationError):
        PublishReviewRequest(
            track_id=10,
            rating=rating,
            text=text,
        )


def test_default_factory_fields_in_responses() -> None:
    action_res = ActionSuccessResponse()
    assert action_res.success is True

    dashboard_res = ExecutiveDashboardResponse(
        total_users=0,
        estimated_net_revenue=0.0,
    )
    assert dashboard_res.users_by_plan == {}
    assert dashboard_res.revenue_by_plan == {}


def test_auth_and_profile_responses_expose_only_english_fields() -> None:
    from app.presentation.schemas.admin import PlanResponse
    from app.presentation.schemas.auth import AuthResponse, UserResponse
    from app.presentation.schemas.discovery import InteractionResponse
    from app.presentation.schemas.profile import UserProfileResponse

    user_res = UserResponse(
        user_id=1,
        email="frog@ribbit.com",
        display_name="Froggy",
        age=20,
        plan_id=2,
        birth_date="2006-01-01",
    )
    assert user_res.user_id == 1
    assert user_res.display_name == "Froggy"
    assert user_res.age == 20
    assert user_res.plan_id == 2
    assert user_res.birth_date == "2006-01-01"

    auth_res = AuthResponse(
        access_token="tok123",
        token_type="bearer",
        user=user_res,
    )
    assert auth_res.user.email == "frog@ribbit.com"

    dumped = auth_res.model_dump()
    assert dumped["access_token"] == "tok123"
    assert dumped["user"]["user_id"] == 1

    profile_res = UserProfileResponse(
        user=user_res,
        plan=PlanResponse(
            plan_id=2, name="Premium", monthly_price=19.9, max_profiles=1
        ),
        recent_interactions=[
            InteractionResponse(interaction_id=1, user_id=1, track_id=10, action="like")
        ],
    )
    assert len(profile_res.recent_interactions) == 1
    assert profile_res.recent_interactions[0].track_id == 10
    assert profile_res.plan.name == "Premium"


def test_register_user_request_rejects_non_english_fields() -> None:
    data = {
        "email": "frog@ribbit.com",
        "senha": "mypassword",
        "nome_exibicao": "Alias Frog",
        "data_nascimento": "2000-05-15",
        "plano_id": 3,
    }
    with pytest.raises(ValidationError):
        RegisterUserRequest.model_validate(data)

    req = RegisterUserRequest.model_validate(
        {
            "email": "frog@ribbit.com",
            "password": "mypassword",
            "display_name": "Alias Frog",
            "birth_date": "2000-05-15",
            "plan_id": 3,
        }
    )
    assert req.display_name == "Alias Frog"


def test_add_family_member_request_provisioning_uses_english_fields() -> None:
    from app.presentation.schemas.profile import AddFamilyMemberRequest

    data = {
        "email": "minor@ribbit.com",
        "password": "minorpassword",
        "display_name": "Tadpole",
        "birth_date": "2015-06-01",
    }
    req = AddFamilyMemberRequest.model_validate(data)
    assert req.email == "minor@ribbit.com"
    assert req.password == "minorpassword"
    assert req.display_name == "Tadpole"
    assert req.birth_date == "2015-06-01"


def test_interaction_request_rejects_duplicate_user_identity_fields() -> None:
    with pytest.raises(ValidationError):
        InteractionRequest.model_validate(
            {"user_id": 1, "track_id": 2, "action": "like"}
        )
