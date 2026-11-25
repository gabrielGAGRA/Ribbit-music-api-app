"""Track catalog search and community reviews router."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.application.dtos import (
    PublishReviewCommand,
    SearchTracksCommand,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.use_cases.discovery import RecordTrackAccessUseCase
from app.application.use_cases.review import (
    DeleteReviewUseCase,
    GetCommunityFeedUseCase,
    GetRecentlyInteractedTracksUseCase,
    GetTrackReviewsUseCase,
    GetUserReviewsUseCase,
    LikeReviewCommentUseCase,
    PublishReviewUseCase,
    SaveSearchTrackLikeUseCase,
    SearchTracksUseCase,
)
from app.domain.models.user import User
from app.presentation.dependencies import (
    get_current_user,
    get_optional_current_user,
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
    RecordTrackAccessRequest,
    RecordTrackAccessResponse,
    ReviewActionResponse,
    ReviewResponse,
    SaveSearchTrackLikeRequest,
)

router = APIRouter(tags=["Tracks & Reviews"])


@router.get("/api/tracks/search", response_model=list[CatalogTrackResponse])
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
            start_year=query.start_year,
            end_year=query.end_year,
            min_rating=query.min_rating,
            sort_by=query.sort_by,
            include_deleted=query.include_deleted,
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
    user_id: Annotated[int, Depends(require_user)],
) -> ReviewResponse:
    review = use_case.execute(
        PublishReviewCommand(
            user_id=user_id,
            track_id=req.track_id,
            rating=req.rating,
            text=req.text,
        )
    )
    return ReviewResponse.model_validate(review)


@router.delete("/api/reviews/{review_id}", response_model=ReviewActionResponse)
def delete_review(
    review_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[DeleteReviewUseCase, Depends(provide(DeleteReviewUseCase))],
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
def get_recently_interacted_tracks(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetRecentlyInteractedTracksUseCase,
        Depends(provide(GetRecentlyInteractedTracksUseCase)),
    ],
    limit: Annotated[int, Query(ge=1, le=5000)] = 20,
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
def save_search_track_like(
    track_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        SaveSearchTrackLikeUseCase,
        Depends(provide(SaveSearchTrackLikeUseCase)),
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
def get_community_feed(
    use_case: Annotated[
        GetCommunityFeedUseCase, Depends(provide(GetCommunityFeedUseCase))
    ],
    track_repo: Annotated[
        TrackRepositoryPort | None, Depends(provide(TrackRepositoryPort))
    ] = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
    days: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    sort_by: Annotated[
        Literal["recent", "oldest", "likes", "rating_desc", "rating_asc"],
        Query(),
    ] = "likes",
) -> list[ReviewResponse]:
    if current_user is not None and current_user.is_minor() and track_repo is not None:
        reviews = use_case.execute(
            days=days, limit=min(100, limit * 5), sort_by=sort_by
        )
        tracks_by_id = track_repo.find_by_ids([r.track_id for r in reviews])
        filtered = [
            r
            for r in reviews
            if (track := tracks_by_id.get(r.track_id)) is not None
            and not track.is_deleted
            and not current_user.is_track_restricted_for_minor(track)
        ][:limit]
        return [ReviewResponse.model_validate(r) for r in filtered]
    reviews = use_case.execute(days=days, limit=limit, sort_by=sort_by)
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.get("/api/reviews/me", response_model=list[ReviewResponse])
def get_my_reviews(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[GetUserReviewsUseCase, Depends(provide(GetUserReviewsUseCase))],
    track_repo: Annotated[
        TrackRepositoryPort | None, Depends(provide(TrackRepositoryPort))
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ReviewResponse]:
    if current_user.user_id is None:
        raise RuntimeError("Authenticated user is missing its persisted ID.")
    reviews = use_case.execute(user_id=current_user.user_id, limit=limit)
    if current_user.is_minor() and track_repo is not None:
        tracks_by_id = track_repo.find_by_ids([r.track_id for r in reviews])
        reviews = [
            r
            for r in reviews
            if (track := tracks_by_id.get(r.track_id)) is not None
            and not track.is_deleted
            and not current_user.is_track_restricted_for_minor(track)
        ]
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.get("/api/reviews/track/{track_id}", response_model=list[ReviewResponse])
def get_track_reviews(
    track_id: int,
    use_case: Annotated[
        GetTrackReviewsUseCase,
        Depends(provide(GetTrackReviewsUseCase)),
    ],
    track_repo: Annotated[
        TrackRepositoryPort | None, Depends(provide(TrackRepositoryPort))
    ] = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    sort_by: Annotated[
        Literal["recent", "oldest", "likes", "rating_desc", "rating_asc"],
        Query(),
    ] = "recent",
) -> list[ReviewResponse]:
    reviews = use_case.execute(track_id=track_id, limit=limit, sort_by=sort_by)
    if current_user is not None and current_user.is_minor() and track_repo is not None:
        track = track_repo.find_by_id(track_id)
        if track is not None and current_user.is_track_restricted_for_minor(track):
            return []
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.post(
    "/api/tracks/{track_id}/access",
    response_model=RecordTrackAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_track_access(
    track_id: int,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        RecordTrackAccessUseCase, Depends(provide(RecordTrackAccessUseCase))
    ],
    req: RecordTrackAccessRequest | None = None,
) -> RecordTrackAccessResponse:
    access = use_case.execute(
        user_id=user_id,
        track_id=track_id,
        source=req.source if req is not None else "play",
    )
    return RecordTrackAccessResponse.model_validate(access)


__all__ = ["router"]
