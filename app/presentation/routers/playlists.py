"""Playlist deck, swipe-add, library, and export router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from starlette.responses import Response

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
    GetPlaylistCoverUseCase,
    GetPlaylistDeckUseCase,
    ListUserPlaylistsUseCase,
    RemoveTrackFromPlaylistUseCase,
    UploadPlaylistCoverUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.presentation.dependencies.auth import require_user
from app.presentation.dependencies.container import get_container, provide
from app.presentation.schemas.common import ActionSuccessResponse
from app.presentation.schemas.playlists import (
    DeckPlaylistRequest,
    PaginatedTracksResponse,
    PlaylistResponse,
    SwipeAddTrackRequest,
    TrackResponse,
)

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])
MAX_COVER_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_SIGNATURES: dict[str, tuple[bytes, int]] = {
    "image/jpeg": (b"\xff\xd8\xff", 0),
    "image/png": (b"\x89PNG\r\n\x1a\n", 0),
    "image/webp": (b"WEBP", 8),
}


def _is_valid_image(content_type: str, image_data: bytes) -> bool:
    signature = _IMAGE_SIGNATURES.get(content_type)
    if signature is None:
        return False
    expected, offset = signature
    if content_type == "image/webp":
        return image_data[:4] == b"RIFF" and image_data[offset : offset + 4] == expected
    return image_data.startswith(expected)


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


async def _read_limited_image(request: Request) -> bytes:
    content_type = (
        request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    )
    if content_type not in _IMAGE_SIGNATURES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use a JPEG, PNG, or WebP image.",
        )

    chunks: list[bytes] = []
    total_size = 0
    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > MAX_COVER_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Playlist images must be 5 MB or smaller.",
            )
        chunks.append(chunk)

    image_data = b"".join(chunks)
    if not _is_valid_image(content_type, image_data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded data does not match its image content type.",
        )
    return image_data


@router.put("/{playlist_id}/image", response_model=PlaylistResponse)
async def upload_playlist_image(
    playlist_id: int,
    request: Request,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        UploadPlaylistCoverUseCase,
        Depends(provide(UploadPlaylistCoverUseCase)),
    ],
) -> PlaylistResponse:
    content_type = (
        request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    )
    image_data = await _read_limited_image(request)
    cover_image_url = f"/api/playlists/{playlist_id}/image"
    playlist = use_case.execute(
        playlist_id=playlist_id,
        user_id=current_user_id,
        content_type=content_type,
        image_data=image_data,
        cover_image_url=cover_image_url,
    )
    return _build_playlist_response(playlist)


@router.get("/{playlist_id}/image")
def get_playlist_image(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetPlaylistCoverUseCase,
        Depends(provide(GetPlaylistCoverUseCase)),
    ],
) -> Response:
    content_type, image_data = use_case.execute(
        playlist_id=playlist_id,
        user_id=current_user_id,
    )
    return Response(
        content=image_data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/deck", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED
)
def create_deck_playlist(
    req: DeckPlaylistRequest,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        CreateDeckPlaylistUseCase, Depends(get_create_deck_playlist_use_case)
    ],
) -> PlaylistResponse:
    playlist = use_case.execute(
        CreateDeckPlaylistCommand(
            user_id=current_user_id,
            name=req.name,
            duration_minutes=req.duration_minutes,
            genre=req.genre,
            year=req.year,
            artist=req.artist,
            country=req.country,
            description=req.description,
            populate_tracks=False,
            reference_playlist_id=req.reference_playlist_id or req.source_playlist_id,
        )
    )
    return _build_playlist_response(playlist)


@router.get("/{playlist_id}/deck", response_model=PaginatedTracksResponse)
def get_playlist_deck(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetPlaylistDeckUseCase, Depends(get_get_playlist_deck_use_case)
    ],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    cursor_id: Annotated[int | None, Query(gt=0)] = None,
) -> PaginatedTracksResponse:
    page_limit = limit if isinstance(limit, int) else 20
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
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        AddTrackToPlaylistUseCase, Depends(get_add_track_to_playlist_use_case)
    ],
) -> ActionSuccessResponse:
    use_case.execute(
        AddTrackToPlaylistCommand(
            playlist_id=playlist_id,
            track_id=req.track_id,
            user_id=current_user_id,
            action=req.action,
        )
    )
    return ActionSuccessResponse(success=True)


@router.get("/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(
    playlist_id: int,
    request: Request,
    current_user_id: Annotated[int, Depends(require_user)],
) -> PlaylistResponse:
    container = get_container(request)
    playlist = container.playlist_repo.find_by_id(playlist_id)
    if not playlist:
        raise EntityNotFoundError(f"Playlist with ID {playlist_id} not found.")
    if not playlist.is_owned_by(current_user_id):
        raise PermissionDeniedError(
            "Access denied: playlist does not belong to this user."
        )
    return _build_playlist_response(playlist)


@router.delete("/{playlist_id}/tracks/{track_id}", response_model=ActionSuccessResponse)
def remove_track(
    playlist_id: int,
    track_id: int,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        RemoveTrackFromPlaylistUseCase,
        Depends(get_remove_track_from_playlist_use_case),
    ],
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
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[DeletePlaylistUseCase, Depends(get_delete_playlist_use_case)],
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
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ListUserPlaylistsUseCase, Depends(get_list_user_playlists_use_case)
    ],
) -> list[PlaylistResponse]:
    playlists = use_case.execute(user_id=current_user_id)
    return [_build_playlist_response(p) for p in playlists]


@router.post(
    "/{playlist_id}/export-spotify",
    response_model=PlaylistResponse,
)
def export_playlist_to_spotify(
    playlist_id: int,
    current_user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ExportPlaylistToSpotifyUseCase,
        Depends(get_export_playlist_to_spotify_use_case),
    ],
) -> PlaylistResponse:
    playlist = use_case.execute(
        user_id=current_user_id,
        playlist_id=playlist_id,
    )
    return _build_playlist_response(playlist)


__all__ = ["router"]
