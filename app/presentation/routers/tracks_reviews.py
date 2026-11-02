"""Track catalog search and community reviews router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.application.dtos import (
    PublishReviewCommand,
    SearchTracksCommand,
)
from app.application.use_cases.review import (
    DeleteReviewUseCase,
    GetCommunityFeedUseCase,
    GetRecentlyInteractedTracksUseCase,
    GetTrackReviewsUseCase,
    LikeReviewCommentUseCase,
    PublishReviewUseCase,
    SaveSearchTrackLikeUseCase,
    SearchTracksUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.presentation.dependencies import (
    get_container,
    provide,
    require_user,
)
from app.presentation.schemas.discovery import (
    InteractionResponse,
    TrackSearchQuery,
)
from app.presentation.schemas.tracks_reviews import (
    CatalogTrackResponse,
    PublishReviewRequest,
    RecentInteractedTrackResponse,
    ReviewActionResponse,
    ReviewResponse,
    SaveSearchTrackLikeRequest,
    TrackReviewListResponse,
)

router = APIRouter(tags=["Tracks & Reviews"])


def _get_delete_review_use_case(request: Request) -> DeleteReviewUseCase:
    container = get_container(request)
    try:
        return container.resolve(DeleteReviewUseCase)
    except KeyError:
        return DeleteReviewUseCase(review_repo=container.review_repo)


def _get_recently_interacted_tracks_use_case(
    request: Request,
) -> GetRecentlyInteractedTracksUseCase:
    container = get_container(request)
    try:
        return container.resolve(GetRecentlyInteractedTracksUseCase)
    except KeyError:
        return GetRecentlyInteractedTracksUseCase(
            user_repo=container.user_repo,
            interaction_repo=container.interaction_repo,
            track_repo=container.track_repo,
        )


def _get_save_search_track_like_use_case(
    request: Request,
) -> SaveSearchTrackLikeUseCase:
    container = get_container(request)
    try:
        return container.resolve(SaveSearchTrackLikeUseCase)
    except KeyError:
        return SaveSearchTrackLikeUseCase(
            user_repo=container.user_repo,
            track_repo=container.track_repo,
            interaction_repo=container.interaction_repo,
            playlist_repo=container.playlist_repo,
        )


@router.get("/api/tracks/search", response_model=list[CatalogTrackResponse])
@router.get("/api/musicas/buscar", response_model=list[CatalogTrackResponse])
def search_tracks(
    user_id: Annotated[int, Depends(require_user)],
    query: Annotated[TrackSearchQuery, Depends()],
    use_case: Annotated[SearchTracksUseCase, Depends(provide(SearchTracksUseCase))],
    termo: Annotated[str | None, Query()] = None,
) -> list[CatalogTrackResponse]:
    search_query = query.query or termo
    tracks = use_case.execute(
        SearchTracksCommand(
            user_id=user_id,
            query=search_query,
            artist=query.artist,
            album=query.album,
            genre=query.genre,
            year=query.year,
            limit=query.limit,
            offset=query.offset,
        )
    )
    return [CatalogTrackResponse.model_validate(t) for t in tracks]


@router.post(
    "/api/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_review(
    req: PublishReviewRequest,
    use_case: Annotated[PublishReviewUseCase, Depends(provide(PublishReviewUseCase))],
    user_id: Annotated[int, Depends(require_user)] = 0,
) -> ReviewResponse:
    effective_user_id = req.user_id if req.user_id is not None else user_id
    review = use_case.execute(
        PublishReviewCommand(
            user_id=effective_user_id,
            track_id=req.resolved_track_id,
            rating=req.resolved_rating,
            text=req.resolved_text,
        )
    )
    return ReviewResponse.model_validate(review)


@router.delete("/api/reviews/{review_id}", response_model=ReviewActionResponse)
def delete_review(
    review_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[DeleteReviewUseCase, Depends(_get_delete_review_use_case)],
) -> ReviewActionResponse:
    success = use_case.execute(review_id=review_id, user_id=user_id)
    return ReviewActionResponse(success=success, sucesso=success)


@router.post("/api/reviews/{review_id}/like", response_model=ReviewResponse)
def like_review(
    review_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        LikeReviewCommentUseCase, Depends(provide(LikeReviewCommentUseCase))
    ],
) -> ReviewResponse:
    review = use_case.execute(review_id=review_id, user_id=user_id)
    return ReviewResponse.model_validate(review)


@router.get(
    "/api/reviews/recent-interacted",
    response_model=list[RecentInteractedTrackResponse],
)
@router.get(
    "/api/reviews/ultimas-interagidas",
    response_model=list[RecentInteractedTrackResponse],
)
def get_recently_interacted_tracks(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetRecentlyInteractedTracksUseCase,
        Depends(_get_recently_interacted_tracks_use_case),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RecentInteractedTrackResponse]:
    items = use_case.execute(user_id=user_id, limit=limit)
    return [
        RecentInteractedTrackResponse(
            interaction=InteractionResponse.model_validate(item.interaction),
            track=CatalogTrackResponse.model_validate(item.track),
        )
        for item in items
    ]


@router.post(
    "/api/reviews/{track_id}/like-and-save", response_model=ReviewActionResponse
)
@router.post(
    "/api/reviews/{track_id}/curtir-busca", response_model=ReviewActionResponse
)
def save_search_track_like(
    track_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        SaveSearchTrackLikeUseCase,
        Depends(_get_save_search_track_like_use_case),
    ],
    req: SaveSearchTrackLikeRequest | None = None,
) -> ReviewActionResponse:
    playlist_id = req.playlist_id if req is not None else None
    success = use_case.execute(
        user_id_or_cmd=user_id,
        track_id=track_id,
        playlist_id=playlist_id,
    )
    return ReviewActionResponse(success=success, sucesso=success)


@router.get("/api/reviews/feed", response_model=list[ReviewResponse])
@router.get("/api/reviews/feed-top5dias", response_model=list[ReviewResponse])
def get_community_feed(
    use_case: Annotated[
        GetCommunityFeedUseCase, Depends(provide(GetCommunityFeedUseCase))
    ],
    days: Annotated[int, Query(ge=1)] = 5,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[ReviewResponse]:
    reviews = use_case.execute(days=days, limit=limit)
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.get("/api/reviews/track/{track_id}", response_model=list[ReviewResponse])
def get_track_reviews(
    track_id: int,
    use_case: Annotated[
        GetTrackReviewsUseCase, Depends(provide(GetTrackReviewsUseCase))
    ],
) -> list[ReviewResponse]:
    reviews = use_case.execute(track_id=track_id)
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.get("/api/reviews/musica/{musica_id}", response_model=TrackReviewListResponse)
def get_musica_reviews(
    musica_id: int,
    request: Request,
    use_case: Annotated[
        GetTrackReviewsUseCase, Depends(provide(GetTrackReviewsUseCase))
    ],
) -> TrackReviewListResponse:
    track = get_container(request).track_repo.find_by_id(musica_id)
    if not track or track.is_deleted:
        raise EntityNotFoundError(
            f"Música com ID {musica_id} não encontrada ou inativa."
        )
    reviews = use_case.execute(track_id=musica_id)
    return TrackReviewListResponse(
        track=CatalogTrackResponse.model_validate(track),
        reviews=[ReviewResponse.model_validate(r) for r in reviews],
    )


__all__ = ["router"]
