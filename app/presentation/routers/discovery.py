"""Discovery and swipe interaction router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.application.dtos import RecordSwipeCommand
from app.application.use_cases.discovery import (
    GetNextDiscoveryTrackUseCase,
    RecordSwipeInteractionUseCase,
    UndoLatestDiscoveryInteractionUseCase,
)
from app.domain.models.interaction import InteractionAction
from app.presentation.dependencies import get_container, provide, require_user
from app.presentation.schemas import (
    InteractionRequest,
    InteractionResponse,
    TrackResponse,
    UndoInteractionResponse,
)

router = APIRouter(tags=["Discovery"])


def get_undo_discovery_interaction_use_case(
    request: Request,
) -> UndoLatestDiscoveryInteractionUseCase:
    container = get_container(request)
    return UndoLatestDiscoveryInteractionUseCase(
        user_repo=container.user_repo,
        plan_repo=container.plan_repo,
        interaction_repo=container.interaction_repo,
    )


@router.get("/api/discovery/next", response_model=TrackResponse | None)
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
def record_interaction(
    req: InteractionRequest,
    use_case: Annotated[
        RecordSwipeInteractionUseCase,
        Depends(provide(RecordSwipeInteractionUseCase)),
    ],
    user_id: Annotated[int, Depends(require_user)],
) -> InteractionResponse:
    action = (
        InteractionAction(req.action.lower())
        if isinstance(req.action, str)
        else req.action
    )
    interaction = use_case.execute(
        RecordSwipeCommand(
            user_id=user_id,
            track_id=req.track_id,
            action=action,
        )
    )
    return InteractionResponse.model_validate(interaction)


@router.post("/api/discovery/undo", response_model=UndoInteractionResponse)
def undo_latest_discovery_interaction(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        UndoLatestDiscoveryInteractionUseCase,
        Depends(get_undo_discovery_interaction_use_case),
    ],
) -> UndoInteractionResponse:
    interaction = use_case.execute(user_id=user_id)
    if interaction.interaction_id is None:
        raise RuntimeError("Undone discovery interaction is missing its persisted ID.")
    return UndoInteractionResponse(
        interaction_id=interaction.interaction_id,
        track_id=interaction.track_id,
        action=interaction.action.value,
        created_at=interaction.created_at,
    )


__all__ = ["router"]
