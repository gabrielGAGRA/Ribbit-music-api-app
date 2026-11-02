"""Playlist deck, swipe-add, library, and export router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.application.dtos.playlist_dtos import (
    AddTrackToPlaylistCommand,
    CreateDeckPlaylistCommand,
    DeletePlaylistCommand,
    GetPlaylistDeckCommand,
    RemoveTrackFromPlaylistCommand,
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
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.presentation.dependencies.auth import require_user
from app.presentation.dependencies.container import get_container
from app.presentation.schemas.common import ActionSuccessResponse
from app.presentation.schemas.playlists import (
    DeckPlaylistRequest,
    PaginatedTracksResponse,
    PlaylistResponse,
    SwipeAddTrackRequest,
    TrackResponse,
)

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


def get_create_deck_playlist_use_case(request: Request) -> CreateDeckPlaylistUseCase:
    container = get_container(request)
    try:
        return container.resolve(CreateDeckPlaylistUseCase)
    except KeyError:
        return CreateDeckPlaylistUseCase(
            user_repo=container.user_repo,
            track_repo=container.track_repo,
            playlist_repo=container.playlist_repo,
        )


def get_get_playlist_deck_use_case(request: Request) -> GetPlaylistDeckUseCase:
    container = get_container(request)
    try:
        return container.resolve(GetPlaylistDeckUseCase)
    except KeyError:
        return GetPlaylistDeckUseCase(
            user_repo=container.user_repo,
            playlist_repo=container.playlist_repo,
            track_repo=container.track_repo,
            interaction_repo=container.interaction_repo,
        )


def get_add_track_to_playlist_use_case(request: Request) -> AddTrackToPlaylistUseCase:
    container = get_container(request)
    try:
        return container.resolve(AddTrackToPlaylistUseCase)
    except KeyError:
        return AddTrackToPlaylistUseCase(
            user_repo=container.user_repo,
            track_repo=container.track_repo,
            playlist_repo=container.playlist_repo,
            interaction_repo=container.interaction_repo,
        )


def get_remove_track_from_playlist_use_case(
    request: Request,
) -> RemoveTrackFromPlaylistUseCase:
    container = get_container(request)
    try:
        return container.resolve(RemoveTrackFromPlaylistUseCase)
    except KeyError:
        return RemoveTrackFromPlaylistUseCase(
            user_repo=container.user_repo,
            playlist_repo=container.playlist_repo,
        )


def get_delete_playlist_use_case(request: Request) -> DeletePlaylistUseCase:
    container = get_container(request)
    try:
        return container.resolve(DeletePlaylistUseCase)
    except KeyError:
        return DeletePlaylistUseCase(
            user_repo=container.user_repo,
            playlist_repo=container.playlist_repo,
        )


def get_list_user_playlists_use_case(request: Request) -> ListUserPlaylistsUseCase:
    container = get_container(request)
    try:
        return container.resolve(ListUserPlaylistsUseCase)
    except KeyError:
        return ListUserPlaylistsUseCase(
            playlist_repo=container.playlist_repo,
            user_repo=container.user_repo,
        )


def get_export_playlist_to_spotify_use_case(
    request: Request,
) -> ExportPlaylistToSpotifyUseCase:
    container = get_container(request)
    try:
        return container.resolve(ExportPlaylistToSpotifyUseCase)
    except KeyError:
        return ExportPlaylistToSpotifyUseCase(
            playlist_repo=container.playlist_repo,
            user_repo=container.user_repo,
            export_port=container.music_service,
        )


def _build_playlist_response(playlist: object) -> PlaylistResponse:
    res = PlaylistResponse.model_validate(playlist)
    if hasattr(playlist, "total_duration_seconds"):
        res.total_duration_seconds = playlist.total_duration_seconds
    elif res.tracks:
        res.total_duration_seconds = sum(t.duration_seconds for t in res.tracks)
    return res


@router.post(
    "/deck", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED
)
def create_deck_playlist(
    req: DeckPlaylistRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        CreateDeckPlaylistUseCase, Depends(get_create_deck_playlist_use_case)
    ] = None,  # type: ignore[assignment]
) -> PlaylistResponse:
    effective_user_id = current_user_id or req.user_id or 0
    # In deck creation mode via API, initial tracks should be empty to allow swipe discovery
    populate = req.user_id is not None and not current_user_id
    playlist = use_case.execute(
        CreateDeckPlaylistCommand(
            user_id=effective_user_id,
            name=req.name,
            duration_minutes=req.duration_minutes,
            genre=req.genre,
            year=req.year,
            artist=req.artist,
            country=req.country,
            description=req.description,
            populate_tracks=populate,
        )
    )
    return _build_playlist_response(playlist)


@router.get("/{playlist_id}/deck", response_model=PaginatedTracksResponse)
def get_playlist_deck(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    limite: Annotated[int | None, Query(ge=1, le=100)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    cursor_id: Annotated[int | None, Query(gt=0)] = None,
    use_case: Annotated[
        GetPlaylistDeckUseCase, Depends(get_get_playlist_deck_use_case)
    ] = None,  # type: ignore[assignment]
) -> PaginatedTracksResponse:
    page_limit = (
        limit if isinstance(limit, int) else (limite if isinstance(limite, int) else 20)
    )
    cursor_val = cursor_id if isinstance(cursor_id, int) else None
    deck_result = use_case.execute(
        GetPlaylistDeckCommand(
            playlist_id=playlist_id,
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


@router.post("/{playlist_id}/swipe-add", response_model=ActionSuccessResponse)
def swipe_add_track(
    playlist_id: int,
    req: SwipeAddTrackRequest,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    user_id: Annotated[int | None, Query()] = None,
    use_case: Annotated[
        AddTrackToPlaylistUseCase, Depends(get_add_track_to_playlist_use_case)
    ] = None,  # type: ignore[assignment]
) -> ActionSuccessResponse:
    effective_user_id = current_user_id or user_id or 0
    use_case.execute(
        AddTrackToPlaylistCommand(
            playlist_id=playlist_id,
            track_id=req.track_id,
            user_id=effective_user_id,
            action=req.action,
        )
    )
    return ActionSuccessResponse(success=True)


@router.get("/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(
    playlist_id: int,
    request: Request,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
) -> PlaylistResponse:
    container = get_container(request)
    playlist = container.playlist_repo.find_by_id(playlist_id)
    if not playlist:
        raise EntityNotFoundError(f"Playlist with ID {playlist_id} not found.")
    if current_user_id and not playlist.is_owned_by(current_user_id):
        raise PermissionDeniedError(
            "Access denied: playlist does not belong to this user."
        )
    return _build_playlist_response(playlist)


@router.delete("/{playlist_id}/tracks/{track_id}", response_model=ActionSuccessResponse)
@router.delete(
    "/{playlist_id}/musicas/{track_id}",
    response_model=ActionSuccessResponse,
    include_in_schema=False,
)
def remove_track(
    playlist_id: int,
    track_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        RemoveTrackFromPlaylistUseCase,
        Depends(get_remove_track_from_playlist_use_case),
    ] = None,  # type: ignore[assignment]
) -> ActionSuccessResponse:
    success = use_case.execute(
        RemoveTrackFromPlaylistCommand(
            playlist_id=playlist_id,
            track_id=track_id,
            user_id=current_user_id,
        )
    )
    return ActionSuccessResponse(success=success)


@router.delete("/{playlist_id}", response_model=ActionSuccessResponse)
def delete_playlist(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    use_case: Annotated[
        DeletePlaylistUseCase, Depends(get_delete_playlist_use_case)
    ] = None,  # type: ignore[assignment]
) -> ActionSuccessResponse:
    success = use_case.execute(
        DeletePlaylistCommand(
            playlist_id=playlist_id,
            user_id=current_user_id,
        )
    )
    return ActionSuccessResponse(success=success)


@router.get("", response_model=list[PlaylistResponse])
def list_playlists(
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    user_id: Annotated[int | None, Query()] = None,
    use_case: Annotated[
        ListUserPlaylistsUseCase, Depends(get_list_user_playlists_use_case)
    ] = None,  # type: ignore[assignment]
) -> list[PlaylistResponse]:
    effective_user_id = current_user_id or user_id or 0
    playlists = use_case.execute(user_id=effective_user_id)
    return [_build_playlist_response(p) for p in playlists]


@router.post(
    "/{playlist_id}/export-spotify",
    response_model=PlaylistResponse,
)
@router.post(
    "/{playlist_id}/exportar-spotify",
    response_model=PlaylistResponse,
    include_in_schema=False,
)
def export_playlist_to_spotify(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)] = 0,
    user_id: Annotated[int | None, Query()] = None,
    use_case: Annotated[
        ExportPlaylistToSpotifyUseCase,
        Depends(get_export_playlist_to_spotify_use_case),
    ] = None,  # type: ignore[assignment]
) -> PlaylistResponse:
    effective_user_id = current_user_id or user_id or 0
    playlist = use_case.execute(
        user_id=effective_user_id,
        playlist_id=playlist_id,
    )
    return _build_playlist_response(playlist)


__all__ = ["router"]
