"""Discovery and swipe interaction router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.dtos import RecordSwipeCommand
from app.application.use_cases.discovery import (
    GetNextDiscoveryTrackUseCase,
    RecordSwipeInteractionUseCase,
)
from app.domain.exceptions import AuthenticationRequiredError
from app.domain.models.interaction import InteractionAction
from app.presentation.dependencies import provide, require_user
from app.presentation.schemas import (
    InteractionRequest,
    InteractionResponse,
    TrackResponse,
)

router = APIRouter(tags=["Discovery"])


@router.get("/api/discovery/next", response_model=TrackResponse | None)
@router.get(
    "/api/discovery/proxima",
    response_model=TrackResponse | None,
    include_in_schema=False,
)
@router.get(
    "/api/descoberta/proxima",
    response_model=TrackResponse | None,
    include_in_schema=False,
)
def get_next_track(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetNextDiscoveryTrackUseCase, Depends(provide(GetNextDiscoveryTrackUseCase))
    ],
) -> TrackResponse | None:
    track = use_case.execute(user_id=user_id)
    if not track:
        return None
    return TrackResponse.model_validate(track)


@router.post("/api/discovery/interact", response_model=InteractionResponse)
@router.post("/api/discovery/interactions", response_model=InteractionResponse)
@router.post(
    "/api/discovery/interagir",
    response_model=InteractionResponse,
    include_in_schema=False,
)
@router.post(
    "/api/descoberta/interagir",
    response_model=InteractionResponse,
    include_in_schema=False,
)
def record_interaction(
    req: InteractionRequest,
    use_case: Annotated[
        RecordSwipeInteractionUseCase,
        Depends(provide(RecordSwipeInteractionUseCase)),
    ],
    auth_user_id: Annotated[int, Depends(require_user)] = 0,
) -> InteractionResponse:
    uid = auth_user_id or req.user_id
    if not uid:
        raise AuthenticationRequiredError("Authentication required.")
    action = (
        InteractionAction(req.action.lower())
        if isinstance(req.action, str)
        else req.action
    )
    interaction = use_case.execute(
        RecordSwipeCommand(
            user_id=uid,
            track_id=req.track_id,
            action=action,
        )
    )
    return InteractionResponse.model_validate(interaction)


__all__ = ["router"]
