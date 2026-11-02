"""Collaborative Jam session, queue voting, and playback router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.application.dtos.jam_dtos import (
    CloseJamCommand,
    CreateJamCommand,
    GetJamDeckCommand,
    SaveQueueTrackCommand,
    SkipVoteResult,
    VoteJamTrackCommand,
    VoteSkipJamTrackCommand,
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
from app.presentation.dependencies.auth import require_user
from app.presentation.dependencies.container import get_container
from app.presentation.schemas.common import ActionSuccessResponse
from app.presentation.schemas.jams import (
    CreateJamRequest,
    JamQueueItemResponse,
    JamResponse,
    JamStateResponse,
    JoinJamRequest,
    SaveQueueTrackRequest,
    SkipJamTrackRequest,
    SkipVoteResponse,
    VoteJamTrackRequest,
)
from app.presentation.schemas.playlists import (
    PaginatedTracksResponse,
    TrackResponse,
)

router = APIRouter(prefix="/api/jams", tags=["Collaborative Jams"])


def get_create_jam_use_case(request: Request) -> CreateJamUseCase:
    container = get_container(request)
    try:
        return container.resolve(CreateJamUseCase)
    except KeyError:
        return CreateJamUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            playlist_repo=container.playlist_repo,
        )


def get_join_jam_use_case(request: Request) -> JoinJamUseCase:
    container = get_container(request)
    try:
        return container.resolve(JoinJamUseCase)
    except KeyError:
        return JoinJamUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
        )


def get_jam_deck_use_case(request: Request) -> GetJamDeckUseCase:
    container = get_container(request)
    try:
        return container.resolve(GetJamDeckUseCase)
    except KeyError:
        return GetJamDeckUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            track_repo=container.track_repo,
            playlist_repo=container.playlist_repo,
            interaction_repo=container.interaction_repo,
        )


def get_vote_jam_track_use_case(request: Request) -> VoteJamTrackUseCase:
    container = get_container(request)
    try:
        return container.resolve(VoteJamTrackUseCase)
    except KeyError:
        return VoteJamTrackUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            track_repo=container.track_repo,
        )


def get_vote_skip_jam_track_use_case(request: Request) -> VoteSkipJamTrackUseCase:
    container = get_container(request)
    try:
        return container.resolve(VoteSkipJamTrackUseCase)
    except KeyError:
        return VoteSkipJamTrackUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            track_repo=container.track_repo,
        )


def get_advance_jam_playback_use_case(request: Request) -> AdvanceJamPlaybackUseCase:
    container = get_container(request)
    try:
        return container.resolve(AdvanceJamPlaybackUseCase)
    except KeyError:
        return AdvanceJamPlaybackUseCase(
            jam_repo=container.jam_repo,
            track_repo=container.track_repo,
        )


def get_save_queue_track_use_case(request: Request) -> SaveQueueTrackUseCase:
    container = get_container(request)
    try:
        return container.resolve(SaveQueueTrackUseCase)
    except KeyError:
        return SaveQueueTrackUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            track_repo=container.track_repo,
            interaction_repo=container.interaction_repo,
            playlist_repo=container.playlist_repo,
        )


def get_close_jam_use_case(request: Request) -> CloseJamUseCase:
    container = get_container(request)
    try:
        return container.resolve(CloseJamUseCase)
    except KeyError:
        return CloseJamUseCase(
            jam_repo=container.jam_repo,
        )


def get_jam_state_use_case(request: Request) -> GetJamStateUseCase:
    container = get_container(request)
    try:
        return container.resolve(GetJamStateUseCase)
    except KeyError:
        return GetJamStateUseCase(
            jam_repo=container.jam_repo,
            user_repo=container.user_repo,
            track_repo=container.track_repo,
        )


@router.post("", response_model=JamResponse, status_code=status.HTTP_201_CREATED)
def create_jam(
    req: CreateJamRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[CreateJamUseCase, Depends(get_create_jam_use_case)] = None,  # type: ignore[assignment]
) -> JamResponse:
    host_id = current_user_id or req.host_user_id or 0
    jam = use_case.execute(
        CreateJamCommand(
            host_user_id=host_id,
            room_name=req.room_name,
            duration_minutes=req.duration_minutes,
            max_superlikes=req.max_superlikes,
            skip_votes_threshold=req.skip_votes_threshold,
            deck_source=req.deck_source,
            source_playlist_id=req.source_playlist_id,
        )
    )
    return JamResponse.model_validate(jam)


@router.post("/join", response_model=JamResponse)
@router.post("/entrar", response_model=JamResponse, include_in_schema=False)
def join_jam(
    req: JoinJamRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[JoinJamUseCase, Depends(get_join_jam_use_case)] = None,  # type: ignore[assignment]
) -> JamResponse:
    if current_user_id:
        jam = use_case.execute(room_code=req.room_code, user_id=current_user_id)
    else:
        jam = use_case.execute(room_code=req.room_code)
    return JamResponse.model_validate(jam)


@router.get("/{jam_id}/state", response_model=JamStateResponse)
@router.get(
    "/{jam_id}/estado", response_model=JamStateResponse, include_in_schema=False
)
def get_jam_state(
    jam_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    user_id: Annotated[int | None, Query()] = None,
    use_case: Annotated[GetJamStateUseCase, Depends(get_jam_state_use_case)] = None,  # type: ignore[assignment]
) -> JamStateResponse:
    effective_user_id = current_user_id or user_id or 0
    state = use_case.execute(jam_id=jam_id, user_id=effective_user_id)
    if isinstance(state, dict):
        return JamStateResponse(
            jam=JamResponse.model_validate(state["jam"]),
            current_track=(
                TrackResponse.model_validate(state["current_track"])
                if state.get("current_track")
                else None
            ),
            queue=[
                JamQueueItemResponse.model_validate(item)
                for item in state.get("queue", [])
            ],
            skip_votes=state.get("skip_votes") or state.get("votos_pular") or 0,
        )
    return JamStateResponse(
        jam=JamResponse.model_validate(state.jam),
        current_track=(
            TrackResponse.model_validate(state.current_track)
            if state.current_track
            else None
        ),
        queue=[JamQueueItemResponse.model_validate(item) for item in state.queue],
        skip_votes=getattr(state, "skip_votes", 0),
    )


@router.post("/{jam_id}/deck-vote", response_model=JamQueueItemResponse)
@router.post(
    "/{jam_id}/interagir-deck",
    response_model=JamQueueItemResponse,
    include_in_schema=False,
)
@router.post(
    "/{jam_id}/vote", response_model=JamQueueItemResponse, include_in_schema=False
)
def vote_jam_track(
    jam_id: int,
    req: VoteJamTrackRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        VoteJamTrackUseCase, Depends(get_vote_jam_track_use_case)
    ] = None,  # type: ignore[assignment]
) -> JamQueueItemResponse:
    effective_user_id = current_user_id or req.user_id or 0
    queue_item = use_case.execute(
        VoteJamTrackCommand(
            jam_id=jam_id,
            track_id=req.track_id,
            user_id=effective_user_id,
            points=req.points,
            action=req.action,
        )
    )
    return JamQueueItemResponse.model_validate(queue_item)


@router.post("/{jam_id}/skip-vote", response_model=SkipVoteResponse)
@router.post(
    "/{jam_id}/votar-pular",
    response_model=SkipVoteResponse,
    include_in_schema=False,
)
@router.post("/{jam_id}/skip", response_model=SkipVoteResponse, include_in_schema=False)
def skip_jam_track(
    jam_id: int,
    req: SkipJamTrackRequest | None = None,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        VoteSkipJamTrackUseCase, Depends(get_vote_skip_jam_track_use_case)
    ] = None,  # type: ignore[assignment]
) -> SkipVoteResponse:
    req_track_id = req.track_id if req else None
    req_user_id = req.user_id if req else None
    effective_user_id = current_user_id or req_user_id or 0
    result = use_case.execute(
        VoteSkipJamTrackCommand(
            jam_id=jam_id,
            track_id=req_track_id,
            user_id=effective_user_id,
        )
    )
    if isinstance(result, SkipVoteResult):
        return SkipVoteResponse(
            jam_id=result.jam_id,
            track_id=result.track_id,
            votes=result.votes,
            threshold=result.threshold,
            advanced=result.advanced,
            is_active=result.is_active,
            success=result.success,
        )
    if isinstance(result, dict):
        return SkipVoteResponse(
            jam_id=result.get("jam_id", jam_id),
            track_id=result.get("track_id") or result.get("musica_id") or 0,
            votes=result.get("votes") or result.get("votos") or 0,
            threshold=result.get("threshold") or result.get("meta") or 3,
            advanced=result.get("advanced") or result.get("avancou") or False,
            is_active=result.get("is_active") or result.get("jam_ativa") or True,
            success=result.get("success", True),
        )
    # If legacy JamQueueItem returned:
    return SkipVoteResponse(
        jam_id=jam_id,
        track_id=getattr(result, "track_id", 0),
        votes=getattr(result, "vote_points", 0),
        threshold=3,
        advanced=False,
        is_active=True,
        success=True,
    )


@router.get("/{jam_id}/deck", response_model=PaginatedTracksResponse)
@router.get(
    "/{jam_id}/deck-adicionar",
    response_model=PaginatedTracksResponse,
    include_in_schema=False,
)
def get_jam_deck(
    jam_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    limite: Annotated[int | None, Query(ge=1, le=100)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    cursor_id: Annotated[int | None, Query(gt=0)] = None,
    use_case: Annotated[GetJamDeckUseCase, Depends(get_jam_deck_use_case)] = None,  # type: ignore[assignment]
) -> PaginatedTracksResponse:
    page_limit = (
        limit if isinstance(limit, int) else (limite if isinstance(limite, int) else 20)
    )
    cursor_val = cursor_id if isinstance(cursor_id, int) else None
    deck_result = use_case.execute(
        GetJamDeckCommand(
            jam_id=jam_id,
            user_id=current_user_id,
            limit=page_limit,
            cursor_id=cursor_val,
        )
    )
    return PaginatedTracksResponse(
        items=[TrackResponse.model_validate(t) for t in deck_result.items],
        next_cursor=deck_result.next_cursor,
        has_more=deck_result.has_more,
    )


@router.post("/{jam_id}/save-queue-track", response_model=ActionSuccessResponse)
@router.post(
    "/{jam_id}/curtir-fila",
    response_model=ActionSuccessResponse,
    include_in_schema=False,
)
def save_queue_track(
    jam_id: int,
    req: SaveQueueTrackRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        SaveQueueTrackUseCase, Depends(get_save_queue_track_use_case)
    ] = None,  # type: ignore[assignment]
) -> ActionSuccessResponse:
    success = use_case.execute(
        SaveQueueTrackCommand(
            jam_id=jam_id,
            user_id=current_user_id,
            track_id=req.track_id,
            playlist_id=req.playlist_id,
        )
    )
    return ActionSuccessResponse(success=success)


@router.post("/{jam_id}/close", response_model=JamResponse)
@router.post("/{jam_id}/encerrar", response_model=JamResponse, include_in_schema=False)
def close_jam(
    jam_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[CloseJamUseCase, Depends(get_close_jam_use_case)] = None,  # type: ignore[assignment]
) -> JamResponse:
    jam = use_case.execute(
        CloseJamCommand(
            jam_id=jam_id,
            host_user_id=current_user_id,
        )
    )
    return JamResponse.model_validate(jam)


@router.post("/{jam_id}/advance", response_model=JamResponse)
def advance_jam_playback(
    jam_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    requester_user_id: Annotated[int | None, Query()] = None,
    use_case: Annotated[
        AdvanceJamPlaybackUseCase, Depends(get_advance_jam_playback_use_case)
    ] = None,  # type: ignore[assignment]
) -> JamResponse:
    effective_user_id = current_user_id or requester_user_id or 0
    jam = use_case.execute(
        jam_id=jam_id,
        requester_user_id=effective_user_id,
    )
    return JamResponse.model_validate(jam)


__all__ = ["router"]
