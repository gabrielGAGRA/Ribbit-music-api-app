"""Unit tests for tracks_reviews router functions."""

from unittest.mock import MagicMock

from app.application.dtos.review_dtos import (
    PublishReviewCommand,
    SearchTracksCommand,
    UserTrackInteractionResult,
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
from app.domain.models import (
    Interaction,
    InteractionAction,
    ReviewComment,
    Track,
)
from app.presentation.routers.tracks_reviews import (
    delete_review,
    get_community_feed,
    get_recently_interacted_tracks,
    get_track_reviews,
    like_review,
    publish_review,
    save_search_track_like,
    search_tracks,
)
from app.presentation.schemas.discovery import TrackSearchQuery
from app.presentation.schemas.tracks_reviews import (
    PublishReviewRequest,
    SaveSearchTrackLikeRequest,
)


def test_search_tracks_forwards_command_and_serializes_tracks() -> None:
    mock_use_case = MagicMock(spec=SearchTracksUseCase)
    track = Track(
        track_id=101,
        title="Ribbit Anthem",
        artist="Frog Band",
        duration_seconds=210,
        genre="indie",
        album="Pond Tunes",
        country="BR",
        release_year=2025,
        explicit=False,
    )
    mock_use_case.execute.return_value = [track]
    query = TrackSearchQuery(
        query="Ribbit",
        artist="Frog Band",
        album="Pond Tunes",
        genre="indie",
        year=2025,
        limit=15,
        offset=5,
    )

    res = search_tracks(user_id=7, query=query, use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].track_id == 101
    assert res[0].title == "Ribbit Anthem"
    mock_use_case.execute.assert_called_once_with(
        SearchTracksCommand(
            user_id=7,
            query="Ribbit",
            artist="Frog Band",
            album="Pond Tunes",
            genre="indie",
            year=2025,
            limit=15,
            offset=5,
        )
    )


def test_publish_review_forwards_command_and_returns_response() -> None:
    mock_use_case = MagicMock(spec=PublishReviewUseCase)
    review = ReviewComment(
        review_id=50,
        user_id=7,
        track_id=101,
        initial_rating=4,
        text="Great bassline!",
        initial_likes_count=0,
    )
    mock_use_case.execute.return_value = review
    req = PublishReviewRequest(
        user_id=7,
        track_id=101,
        rating=4,
        text="Great bassline!",
    )

    res = publish_review(req=req, use_case=mock_use_case)

    assert res.review_id == 50
    assert res.user_id == 7
    assert res.track_id == 101
    assert res.rating == 4
    assert res.text == "Great bassline!"
    mock_use_case.execute.assert_called_once_with(
        PublishReviewCommand(
            user_id=7,
            track_id=101,
            rating=4,
            text="Great bassline!",
        )
    )


def test_delete_review_router_calls_use_case_and_returns_success() -> None:
    mock_use_case = MagicMock(spec=DeleteReviewUseCase)
    mock_use_case.execute.return_value = True

    res = delete_review(review_id=50, user_id=7, use_case=mock_use_case)

    assert res.success is True
    assert res.sucesso is True
    mock_use_case.execute.assert_called_once_with(review_id=50, user_id=7)


def test_get_recently_interacted_tracks_router_returns_response_list() -> None:
    mock_use_case = MagicMock(spec=GetRecentlyInteractedTracksUseCase)
    interaction = Interaction(
        interaction_id=1,
        user_id=7,
        track_id=101,
        action=InteractionAction.LIKE,
    )
    track = Track(
        track_id=101,
        title="Song",
        artist="Artist",
        duration_seconds=200,
        genre="Pop",
    )
    mock_use_case.execute.return_value = [
        UserTrackInteractionResult(interaction=interaction, track=track)
    ]

    res = get_recently_interacted_tracks(user_id=7, use_case=mock_use_case, limit=10)

    assert len(res) == 1
    assert res[0].interaction.interaction_id == 1
    assert res[0].track.track_id == 101
    mock_use_case.execute.assert_called_once_with(user_id=7, limit=10)


def test_save_search_track_like_router_calls_use_case_and_returns_success() -> None:
    mock_use_case = MagicMock(spec=SaveSearchTrackLikeUseCase)
    mock_use_case.execute.return_value = True
    req = SaveSearchTrackLikeRequest(playlist_id=12)

    res = save_search_track_like(
        track_id=101,
        user_id=7,
        req=req,
        use_case=mock_use_case,
    )

    assert res.success is True
    assert res.sucesso is True
    mock_use_case.execute.assert_called_once_with(
        user_id_or_cmd=7,
        track_id=101,
        playlist_id=12,
    )


def test_get_community_feed_accepts_custom_query_params() -> None:
    mock_use_case = MagicMock(spec=GetCommunityFeedUseCase)
    empty_feed: list[ReviewComment] = []
    mock_use_case.execute.return_value = empty_feed

    res = get_community_feed(use_case=mock_use_case, days=14, limit=25)

    assert res == []
    mock_use_case.execute.assert_called_once_with(days=14, limit=25)


def test_get_community_feed_defaults() -> None:
    mock_use_case = MagicMock(spec=GetCommunityFeedUseCase)
    empty_feed: list[ReviewComment] = []
    mock_use_case.execute.return_value = empty_feed

    res = get_community_feed(use_case=mock_use_case)

    assert res == []
    mock_use_case.execute.assert_called_once_with(days=5, limit=10)


def test_like_review_router_passes_review_and_user_id() -> None:
    mock_use_case = MagicMock(spec=LikeReviewCommentUseCase)
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=5,
        text="Awesome!",
        initial_likes_count=1,
    )
    mock_use_case.execute.return_value = review

    res = like_review(review_id=1, user_id=20, use_case=mock_use_case)

    assert res.review_id == 1
    assert res.likes_count == 1
    mock_use_case.execute.assert_called_once_with(review_id=1, user_id=20)


def test_get_track_reviews_returns_mapped_reviews() -> None:
    mock_use_case = MagicMock(spec=GetTrackReviewsUseCase)
    review = ReviewComment(
        review_id=2,
        user_id=12,
        track_id=300,
        initial_rating=5,
        text="Classic!",
        initial_likes_count=3,
    )
    mock_use_case.execute.return_value = [review]

    res = get_track_reviews(track_id=300, use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].review_id == 2
    assert res[0].track_id == 300
    assert res[0].likes_count == 3
    mock_use_case.execute.assert_called_once_with(track_id=300)
