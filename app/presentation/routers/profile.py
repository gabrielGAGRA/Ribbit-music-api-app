"""User profile, subscription plans, premium, and family plan router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

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
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.interaction import InteractionAction
from app.presentation.dependencies import provide, require_user
from app.presentation.dependencies.container import get_container
from app.presentation.schemas import (
    ActionSuccessResponse,
    AddFamilyMemberRequest,
    AnnualStatsResponse,
    BlockedGenresRequest,
    ChangeInteractionRequest,
    ChangePlanRequest,
    FavoriteGenresRequest,
    InteractionResponse,
    LinkSpotifyRequest,
    PlanResponse,
    ThemePreferenceRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)

router = APIRouter(tags=["Profile & Plans"])


@router.get("/api/profile/me", response_model=UserProfileResponse)
def get_profile(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[GetUserProfileUseCase, Depends(provide(GetUserProfileUseCase))],
) -> UserProfileResponse:
    data = use_case.execute(user_id=user_id)
    return UserProfileResponse.model_validate(data)


@router.put("/api/profile/me", response_model=UserResponse)
def update_profile(
    req: UpdateProfileRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[UpdateProfileUseCase, Depends(provide(UpdateProfileUseCase))],
) -> UserResponse:
    user = use_case.execute(
        UpdateProfileCommand(
            user_id=user_id,
            display_name=req.display_name,
            new_password=req.new_password,
            current_password=req.current_password,
        )
    )
    return UserResponse.model_validate(user)


@router.post("/api/profile/link-spotify", response_model=UserResponse)
def link_spotify(
    req: LinkSpotifyRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        LinkSpotifyAccountUseCase, Depends(provide(LinkSpotifyAccountUseCase))
    ],
) -> UserResponse:
    user = use_case.execute(
        user_id=user_id,
        spotify_id=req.spotify_id,
    )
    return UserResponse.model_validate(user)


@router.get("/api/plans", response_model=list[PlanResponse])
def list_plans(
    use_case: Annotated[ListPlansUseCase, Depends(provide(ListPlansUseCase))],
) -> list[PlanResponse]:
    plans = use_case.execute()
    return [PlanResponse.model_validate(p) for p in plans]


@router.put("/api/profile/plan", response_model=UserResponse)
def change_plan(
    req: ChangePlanRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ChangeSubscriptionPlanUseCase,
        Depends(provide(ChangeSubscriptionPlanUseCase)),
    ],
) -> UserResponse:
    user = use_case.execute(
        user_id=user_id,
        new_plan_id=req.new_plan_id,
    )
    return UserResponse.model_validate(user)


@router.delete("/api/profile/plan", response_model=UserResponse)
def cancel_plan(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        CancelSubscriptionPlanUseCase,
        Depends(provide(CancelSubscriptionPlanUseCase)),
    ],
) -> UserResponse:
    user = use_case.execute(user_id=user_id)
    return UserResponse.model_validate(user)


@router.delete("/api/profile/account", response_model=ActionSuccessResponse)
def delete_account(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        DeleteUserAccountUseCase, Depends(provide(DeleteUserAccountUseCase))
    ],
) -> ActionSuccessResponse:
    success = use_case.execute(user_id=user_id)
    return ActionSuccessResponse(success=success)


# --- Premium Routes ---


@router.get("/api/profile/stats", response_model=AnnualStatsResponse)
def get_annual_stats(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetAnnualListeningStatsUseCase,
        Depends(provide(GetAnnualListeningStatsUseCase)),
    ],
) -> AnnualStatsResponse:
    stats = use_case.execute(user_id=user_id)
    return AnnualStatsResponse.model_validate(stats)


@router.put("/api/profile/interaction", response_model=InteractionResponse)
def change_interaction(
    req: ChangeInteractionRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ChangeTrackInteractionUseCase,
        Depends(provide(ChangeTrackInteractionUseCase)),
    ],
) -> InteractionResponse:
    action = InteractionAction(req.new_action.lower())
    interaction = use_case.execute(
        user_id=user_id,
        track_id=req.track_id,
        new_action=action,
    )
    return InteractionResponse.model_validate(interaction)


@router.get("/api/profile/interactions", response_model=list[InteractionResponse])
def list_interactions(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ListUserInteractionsUseCase,
        Depends(provide(ListUserInteractionsUseCase)),
    ],
    category: Annotated[str | None, Query()] = None,
) -> list[InteractionResponse]:
    action = InteractionAction(category.lower()) if category else None
    items = use_case.execute(user_id=user_id, action=action)
    return [InteractionResponse.model_validate(i) for i in items]


@router.get("/api/profile/blocked-genres", response_model=list[str])
def list_blocked_genres(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ListBlockedGenresUseCase, Depends(provide(ListBlockedGenresUseCase))
    ],
) -> list[str]:
    return use_case.execute(user_id=user_id)


@router.put("/api/profile/blocked-genres", response_model=UserResponse)
def update_blocked_genres(
    req: BlockedGenresRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        UpdateBlockedGenresUseCase, Depends(provide(UpdateBlockedGenresUseCase))
    ],
) -> UserResponse:
    if isinstance(req.blocked_genres, str):
        blocked_list = [g.strip() for g in req.blocked_genres.split(",") if g.strip()]
    else:
        blocked_list = [str(g).strip() for g in req.blocked_genres if str(g).strip()]

    user = use_case.execute(
        user_id=user_id,
        blocked_genres=blocked_list,
    )
    return UserResponse.model_validate(user)


@router.get("/api/profile/favorite-genres", response_model=list[str])
def list_favorite_genres(
    request: Request,
    user_id: Annotated[int, Depends(require_user)],
) -> list[str]:
    user = get_container(request).user_repo.find_by_id(user_id)
    if user is None:
        raise EntityNotFoundError(f"User with ID {user_id} not found.")
    return sorted(user.favorite_genres)


@router.put("/api/profile/favorite-genres", response_model=UserResponse)
def update_favorite_genres(
    req: FavoriteGenresRequest,
    request: Request,
    user_id: Annotated[int, Depends(require_user)],
) -> UserResponse:
    user = get_container(request).user_repo.find_by_id(user_id)
    if user is None:
        raise EntityNotFoundError(f"User with ID {user_id} not found.")
    if isinstance(req.favorite_genres, str):
        favorite_list = [
            g.strip() for g in req.favorite_genres.split(",") if g.strip()
        ]
    else:
        favorite_list = [
            str(g).strip() for g in req.favorite_genres if str(g).strip()
        ]
    user.update_favorite_genres(favorite_list)
    saved = get_container(request).user_repo.save(user)
    return UserResponse.model_validate(saved)


@router.get("/api/profile/theme", response_model=str)
def get_preferred_theme(
    request: Request,
    user_id: Annotated[int, Depends(require_user)],
) -> str:
    user = get_container(request).user_repo.find_by_id(user_id)
    if user is None:
        raise EntityNotFoundError(f"User with ID {user_id} not found.")
    return user.preferred_theme


@router.put("/api/profile/theme", response_model=UserResponse)
def update_preferred_theme(
    req: ThemePreferenceRequest,
    request: Request,
    user_id: Annotated[int, Depends(require_user)],
) -> UserResponse:
    user = get_container(request).user_repo.find_by_id(user_id)
    if user is None:
        raise EntityNotFoundError(f"User with ID {user_id} not found.")
    user.update_preferred_theme(req.preferred_theme)
    saved = get_container(request).user_repo.save(user)
    return UserResponse.model_validate(saved)


# --- Family Plan Routes ---


@router.get("/api/profile/family/members", response_model=list[UserResponse])
def list_family_members(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ListFamilyMembersUseCase, Depends(provide(ListFamilyMembersUseCase))
    ],
) -> list[UserResponse]:
    members = use_case.execute(primary_user_id=user_id)
    return [UserResponse.model_validate(m) for m in members]


@router.post("/api/profile/family/members", response_model=UserResponse)
def add_family_member(
    req: AddFamilyMemberRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        AddFamilyMemberUseCase, Depends(provide(AddFamilyMemberUseCase))
    ],
) -> UserResponse:
    if req.email:
        dependent = use_case.execute(
            primary_user_id=user_id,
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            birth_date=req.birth_date,
        )
    else:
        dependent = use_case.execute(
            primary_user_id=user_id,
            dependent_user_id=req.dependent_user_id,
        )
    return UserResponse.model_validate(dependent)


@router.delete("/api/profile/family/members/{member_id}", response_model=UserResponse)
def remove_family_member(
    member_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        RemoveFamilyMemberUseCase, Depends(provide(RemoveFamilyMemberUseCase))
    ],
) -> UserResponse:
    unlinked = use_case.execute(
        primary_user_id=user_id,
        member_user_id=member_id,
    )
    return UserResponse.model_validate(unlinked)


__all__ = ["router"]
