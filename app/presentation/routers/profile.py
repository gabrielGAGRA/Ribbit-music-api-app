"""User profile, subscription plans, premium, and family plan router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

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
from app.domain.models.interaction import InteractionAction
from app.presentation.dependencies import provide, require_user
from app.presentation.schemas import (
    ActionSuccessResponse,
    AddFamilyMemberRequest,
    AnnualStatsResponse,
    BlockedGenresRequest,
    ChangeInteractionRequest,
    ChangePlanRequest,
    InteractionResponse,
    LinkSpotifyRequest,
    PlanResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)

router = APIRouter(tags=["Profile & Plans"])


@router.get("/api/profile/me", response_model=UserProfileResponse)
@router.get(
    "/api/perfil/me", response_model=UserProfileResponse, include_in_schema=False
)
def get_profile(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[GetUserProfileUseCase, Depends(provide(GetUserProfileUseCase))],
) -> UserProfileResponse:
    data = use_case.execute(user_id=user_id)
    return UserProfileResponse.model_validate(data)


@router.put("/api/profile/me", response_model=UserResponse)
@router.put("/api/perfil/me", response_model=UserResponse, include_in_schema=False)
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
    use_case: Annotated[
        LinkSpotifyAccountUseCase, Depends(provide(LinkSpotifyAccountUseCase))
    ],
) -> UserResponse:
    user = use_case.execute(
        user_id=req.user_id,
        spotify_id=req.spotify_id,
    )
    return UserResponse.model_validate(user)


@router.get("/api/plans", response_model=list[PlanResponse])
@router.get("/api/planos", response_model=list[PlanResponse], include_in_schema=False)
@router.get(
    "/api/profile/plans",
    response_model=list[PlanResponse],
    include_in_schema=False,
)
@router.get(
    "/api/perfil/planos",
    response_model=list[PlanResponse],
    include_in_schema=False,
)
def list_plans(
    use_case: Annotated[ListPlansUseCase, Depends(provide(ListPlansUseCase))],
) -> list[PlanResponse]:
    plans = use_case.execute()
    return [PlanResponse.model_validate(p) for p in plans]


@router.post("/api/profile/plan", response_model=UserResponse)
@router.post("/api/perfil/plano", response_model=UserResponse, include_in_schema=False)
@router.put("/api/profile/plan", response_model=UserResponse)
@router.put("/api/perfil/plano", response_model=UserResponse, include_in_schema=False)
def change_plan(
    req: ChangePlanRequest,
    use_case: Annotated[
        ChangeSubscriptionPlanUseCase,
        Depends(provide(ChangeSubscriptionPlanUseCase)),
    ],
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> UserResponse:
    uid = req.user_id or auth_user_id
    user = use_case.execute(
        user_id=uid,
        new_plan_id=req.new_plan_id,
    )
    return UserResponse.model_validate(user)


@router.delete("/api/profile/plan", response_model=UserResponse)
@router.delete(
    "/api/perfil/plano", response_model=UserResponse, include_in_schema=False
)
@router.post("/api/profile/plan/cancel", response_model=UserResponse)
@router.post(
    "/api/perfil/plano/cancelar",
    response_model=UserResponse,
    include_in_schema=False,
)
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
@router.delete(
    "/api/perfil/conta",
    response_model=ActionSuccessResponse,
    include_in_schema=False,
)
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
    use_case: Annotated[
        ChangeTrackInteractionUseCase,
        Depends(provide(ChangeTrackInteractionUseCase)),
    ],
) -> InteractionResponse:
    action = InteractionAction(req.new_action.lower())
    interaction = use_case.execute(
        user_id=req.user_id,
        track_id=req.track_id,
        new_action=action,
    )
    return InteractionResponse.model_validate(interaction)


@router.get("/api/profile/history", response_model=list[InteractionResponse])
def list_history(
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
@router.get(
    "/api/perfil/generos-bloqueados",
    response_model=list[str],
    include_in_schema=False,
)
def list_blocked_genres(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ListBlockedGenresUseCase, Depends(provide(ListBlockedGenresUseCase))
    ],
) -> list[str]:
    return use_case.execute(user_id=user_id)


@router.put("/api/profile/blocked-genres", response_model=UserResponse)
@router.put(
    "/api/perfil/generos-bloqueados",
    response_model=UserResponse,
    include_in_schema=False,
)
def update_blocked_genres(
    req: BlockedGenresRequest,
    use_case: Annotated[
        UpdateBlockedGenresUseCase, Depends(provide(UpdateBlockedGenresUseCase))
    ],
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> UserResponse:
    uid = req.user_id or auth_user_id
    if isinstance(req.blocked_genres, str):
        blocked_list = [g.strip() for g in req.blocked_genres.split(",") if g.strip()]
    else:
        blocked_list = [str(g).strip() for g in req.blocked_genres if str(g).strip()]

    user = use_case.execute(
        user_id=uid,
        blocked_genres=blocked_list,
    )
    return UserResponse.model_validate(user)


# --- Family Plan Routes ---


@router.get("/api/profile/family/members", response_model=list[UserResponse])
@router.get(
    "/api/perfil/familia/membros",
    response_model=list[UserResponse],
    include_in_schema=False,
)
def list_family_members(
    use_case: Annotated[
        ListFamilyMembersUseCase, Depends(provide(ListFamilyMembersUseCase))
    ],
    primary_account_id: Annotated[int | None, Query()] = None,
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> list[UserResponse]:
    pid = primary_account_id or auth_user_id
    members = use_case.execute(primary_user_id=pid)
    return [UserResponse.model_validate(m) for m in members]


@router.post("/api/profile/family/members", response_model=UserResponse)
@router.post(
    "/api/perfil/familia/membros",
    response_model=UserResponse,
    include_in_schema=False,
)
def add_family_member(
    req: AddFamilyMemberRequest,
    use_case: Annotated[
        AddFamilyMemberUseCase, Depends(provide(AddFamilyMemberUseCase))
    ],
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> UserResponse:
    pid = req.primary_account_id or auth_user_id
    if req.email:
        dependent = use_case.execute(
            primary_user_id=pid,
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            birth_date=req.birth_date,
        )
    else:
        dependent = use_case.execute(
            primary_user_id=pid,
            dependent_user_id=req.dependent_user_id,
        )
    return UserResponse.model_validate(dependent)


@router.delete("/api/profile/family/members/{member_id}", response_model=UserResponse)
@router.delete(
    "/api/perfil/familia/membros/{member_id}",
    response_model=UserResponse,
    include_in_schema=False,
)
def remove_family_member(
    member_id: int,
    use_case: Annotated[
        RemoveFamilyMemberUseCase, Depends(provide(RemoveFamilyMemberUseCase))
    ],
    primary_account_id: Annotated[int | None, Query()] = None,
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> UserResponse:
    pid = primary_account_id or auth_user_id
    unlinked = use_case.execute(
        primary_user_id=pid,
        member_user_id=member_id,
    )
    return UserResponse.model_validate(unlinked)


__all__ = ["router"]
