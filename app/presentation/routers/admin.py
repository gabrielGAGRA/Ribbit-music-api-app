"""Administration console router for catalog moderation and executive dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

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
from app.domain.exceptions import BusinessRuleViolationError
from app.presentation.dependencies import (
    get_container,
    provide,
    require_admin,
)
from app.presentation.schemas.admin import (
    AudienceReportResponse,
    BlockTrackRequest,
    ExecutiveDashboardResponse,
    PlanResponse,
    TrackBlockResponse,
    TrackExplicitResponse,
    UpdateAdminRoleRequest,
    UpdatePlanAdminRequest,
    UpdateTrackExplicitRequest,
    UserPlanSummaryResponse,
)
from app.presentation.schemas.auth import LoginRequest, UserResponse
from app.presentation.schemas.tracks_reviews import (
    CatalogTrackResponse,
    ReviewResponse,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Console"])


def _get_list_administrators_use_case(
    request: Request,
) -> ListAdministratorsUseCase:
    container = get_container(request)
    try:
        return container.resolve(ListAdministratorsUseCase)
    except KeyError:
        return ListAdministratorsUseCase(user_repo=container.user_repo)


def _get_update_admin_role_use_case(
    request: Request,
) -> UpdateAdminRoleUseCase:
    container = get_container(request)
    try:
        return container.resolve(UpdateAdminRoleUseCase)
    except KeyError:
        return UpdateAdminRoleUseCase(user_repo=container.user_repo)


def _get_list_blocked_tracks_use_case(
    request: Request,
) -> ListBlockedTracksUseCase:
    container = get_container(request)
    try:
        return container.resolve(ListBlockedTracksUseCase)
    except KeyError:
        return ListBlockedTracksUseCase(track_repo=container.track_repo)


@router.post("/login", response_model=UserResponse)
def login_admin(
    req: LoginRequest,
    use_case: Annotated[
        AuthenticateAdminUseCase, Depends(provide(AuthenticateAdminUseCase))
    ],
) -> UserResponse:
    admin = use_case.execute(
        AuthenticateAdminCommand(email=req.email, password=req.password)
    )
    return UserResponse.model_validate(admin)


@router.get(
    "/dashboard",
    response_model=ExecutiveDashboardResponse,
)
def get_executive_dashboard(
    use_case: Annotated[
        GetExecutiveDashboardUseCase,
        Depends(provide(GetExecutiveDashboardUseCase)),
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> ExecutiveDashboardResponse:
    dashboard = use_case.execute()
    return ExecutiveDashboardResponse.model_validate(dashboard)


@router.get(
    "/users",
    response_model=list[UserPlanSummaryResponse],
)
def list_users(
    use_case: Annotated[
        ListUsersWithPlansUseCase, Depends(provide(ListUsersWithPlansUseCase))
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> list[UserPlanSummaryResponse]:
    users = use_case.execute()
    return [UserPlanSummaryResponse.model_validate(u) for u in users]


@router.get(
    "/audience",
    response_model=AudienceReportResponse,
)
@router.get(
    "/audiencia",
    response_model=AudienceReportResponse,
)
def get_audience_report(
    use_case: Annotated[
        GetAudienceReportUseCase, Depends(provide(GetAudienceReportUseCase))
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> AudienceReportResponse:
    report = use_case.execute()
    return AudienceReportResponse.model_validate(report)


@router.get(
    "/administrators",
    response_model=list[UserResponse],
)
@router.get(
    "/administradores",
    response_model=list[UserResponse],
)
def list_administrators(
    use_case: Annotated[
        ListAdministratorsUseCase, Depends(_get_list_administrators_use_case)
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> list[UserResponse]:
    admins = use_case.execute()
    return [UserResponse.model_validate(a) for a in admins]


@router.put(
    "/administrators/{user_id}",
    response_model=UserResponse,
)
@router.put(
    "/administradores/{user_id}",
    response_model=UserResponse,
)
def update_admin_role(
    user_id: int,
    req: UpdateAdminRoleRequest,
    admin_id: Annotated[int, Depends(require_admin)],
    use_case: Annotated[
        UpdateAdminRoleUseCase, Depends(_get_update_admin_role_use_case)
    ],
) -> UserResponse:
    user = use_case.execute(
        admin_id=admin_id,
        target_user_id=user_id,
        is_admin=req.is_admin,
    )
    return UserResponse.model_validate(user)


@router.get(
    "/blocked-tracks",
    response_model=list[CatalogTrackResponse],
)
@router.get(
    "/musicas-bloqueadas",
    response_model=list[CatalogTrackResponse],
)
def list_blocked_tracks(
    use_case: Annotated[
        ListBlockedTracksUseCase, Depends(_get_list_blocked_tracks_use_case)
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> list[CatalogTrackResponse]:
    tracks = use_case.execute()
    return [CatalogTrackResponse.model_validate(t) for t in tracks]


@router.put(
    "/tracks/{track_id}/block",
    response_model=TrackBlockResponse,
)
@router.put(
    "/musicas/{track_id}/bloquear",
    response_model=TrackBlockResponse,
)
@router.post(
    "/tracks/{track_id}/block",
    response_model=TrackBlockResponse,
)
def block_track(
    track_id: int,
    use_case: Annotated[BlockTrackUseCase, Depends(provide(BlockTrackUseCase))],
    req: BlockTrackRequest | None = None,
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> TrackBlockResponse:
    if req is not None and (req.blocked is not None or req.bloqueada is not None):
        result = use_case.execute(track_id=track_id, blocked=req.is_blocked())
    else:
        result = use_case.execute(track_id=track_id)
    return TrackBlockResponse(track_id=track_id, blocked=result)


@router.put(
    "/tracks/{track_id}/explicit",
    response_model=TrackExplicitResponse,
)
def update_track_explicit(
    track_id: int,
    req: UpdateTrackExplicitRequest,
    use_case: Annotated[
        UpdateTrackExplicitFlagUseCase,
        Depends(provide(UpdateTrackExplicitFlagUseCase)),
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> TrackExplicitResponse:
    explicit = use_case.execute(
        track_id=track_id,
        explicit=req.explicit,
    )
    return TrackExplicitResponse(track_id=track_id, explicit=explicit)


@router.put(
    "/users/{user_id}/promote-admin",
    response_model=UserResponse,
)
def promote_user_to_admin(
    user_id: int,
    use_case: Annotated[
        PromoteUserToAdminUseCase, Depends(provide(PromoteUserToAdminUseCase))
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> UserResponse:
    user = use_case.execute(user_id=user_id)
    return UserResponse.model_validate(user)


@router.get(
    "/plans",
    response_model=list[PlanResponse],
)
@router.get(
    "/planos",
    response_model=list[PlanResponse],
)
def list_plans(
    request: Request,
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> list[PlanResponse]:
    plans = get_container(request).plan_repo.list_all()
    return [PlanResponse.model_validate(p) for p in plans]


@router.put(
    "/plans/{plan_id}",
    response_model=PlanResponse,
)
@router.put(
    "/planos/{plan_id}",
    response_model=PlanResponse,
)
def update_plan(
    plan_id: int,
    req: UpdatePlanAdminRequest,
    use_case: Annotated[
        UpdateSubscriptionPlanUseCase,
        Depends(provide(UpdateSubscriptionPlanUseCase)),
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> PlanResponse:
    command = UpdateSubscriptionPlanCommand(
        plan_id=plan_id,
        new_price=req.resolved_price(),
        new_name=req.resolved_name(),
        max_profiles=req.resolved_max_profiles(),
    )
    try:
        plan = use_case.execute(command)
    except ValueError as exc:
        raise BusinessRuleViolationError(str(exc)) from exc
    return PlanResponse.model_validate(plan)


@router.get(
    "/reviews",
    response_model=list[ReviewResponse],
)
def get_top_moderation_reviews(
    use_case: Annotated[
        GetTopModerationReviewsUseCase,
        Depends(provide(GetTopModerationReviewsUseCase)),
    ],
    admin_id: Annotated[int, Depends(require_admin)] = 0,
) -> list[ReviewResponse]:
    reviews = use_case.execute()
    return [ReviewResponse.model_validate(r) for r in reviews]


__all__ = ["router"]
