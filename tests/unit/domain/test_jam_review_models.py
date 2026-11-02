"""Unit tests for Jam, JamQueueItem, and ReviewComment domain models."""

from datetime import UTC, datetime

import pytest

from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models import Jam, JamQueueItem, ReviewComment


def test_jam_generate_room_code_format() -> None:
    code = Jam.generate_room_code()
    assert len(code) == 6
    assert code.isdigit()


def test_jam_create_and_properties() -> None:
    jam = Jam.create(host_user_id=10, room_name="Friday Chill")
    assert jam.host_user_id == 10
    assert jam.room_name == "Friday Chill"
    assert len(jam.room_code) == 6
    assert jam.room_code.isdigit()
    assert jam.is_active is True
    assert jam.current_track_id is None
    assert jam.is_host(10) is True
    assert jam.is_host(11) is False

    custom_jam = Jam.create(
        host_user_id=10, room_name="Custom Room", room_code="JAM-CUSTOM"
    )
    assert custom_jam.room_code == "JAM-CUSTOM"


def test_jam_blank_room_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Jam room name cannot be blank"):
        Jam.create(host_user_id=1, room_name="   ")


def test_jam_set_current_track_and_close_transitions() -> None:
    jam = Jam.create(host_user_id=1, room_name="Party")
    assert jam.set_current_track(42) is jam
    assert jam.current_track_id == 42

    assert jam.set_current_track(None) is jam
    assert jam.current_track_id is None

    assert jam.close() is jam
    assert jam.is_active is False

    with pytest.raises(
        BusinessRuleViolationError,
        match="Cannot set current track on a closed Jam session",
    ):
        jam.set_current_track(99)


def test_jam_queue_item_construction_and_bounds_validation() -> None:
    now = datetime.now(tz=UTC)
    item = JamQueueItem(
        jam_id=1,
        track_id=10,
        jam_queue_id=5,
        added_at=now,
        initial_vote_points=3,
    )
    assert item.jam_id == 1
    assert item.track_id == 10
    assert item.jam_queue_id == 5
    assert item.added_at == now
    assert item.vote_points == 3

    with pytest.raises(ValueError, match="Vote points must be between -10 and 10"):
        JamQueueItem(jam_id=1, track_id=10, initial_vote_points=11)

    with pytest.raises(ValueError, match="Vote points must be between -10 and 10"):
        JamQueueItem(jam_id=1, track_id=10, initial_vote_points=-11)


def test_jam_queue_item_voting_and_clamping() -> None:
    item = JamQueueItem(jam_id=1, track_id=10)
    assert item.vote_points == 0

    assert item.vote(1) is item
    assert item.vote_points == 1

    item.vote(3)
    assert item.vote_points == 4

    item.vote(20)
    assert item.vote_points == JamQueueItem.MAX_POINTS

    item.vote(-5)
    assert item.vote_points == 5

    item.vote(-50)
    assert item.vote_points == JamQueueItem.MIN_POINTS


def test_review_comment_construction_and_rating_validation() -> None:
    now = datetime.now(tz=UTC)
    review = ReviewComment(
        review_id=1,
        user_id=2,
        track_id=3,
        initial_rating=5,
        text="Masterpiece!",
        initial_likes_count=4,
        created_at=now,
    )
    assert review.review_id == 1
    assert review.user_id == 2
    assert review.track_id == 3
    assert review.rating == 5
    assert review.text == "Masterpiece!"
    assert review.likes_count == 4
    assert review.is_deleted is False
    assert review.created_at == now

    assert ReviewComment.is_valid_rating(1) is True
    assert ReviewComment.is_valid_rating(5) is True
    assert ReviewComment.is_valid_rating(0) is False
    assert ReviewComment.is_valid_rating(6) is False


def test_review_comment_invalid_initial_values_raise_value_error() -> None:
    with pytest.raises(ValueError, match="Rating must be between 1 and 5, got 0"):
        ReviewComment(user_id=1, track_id=1, initial_rating=0)

    with pytest.raises(ValueError, match="Rating must be between 1 and 5, got 6"):
        ReviewComment(user_id=1, track_id=1, initial_rating=6)

    with pytest.raises(ValueError, match="Likes count cannot be negative"):
        ReviewComment(
            user_id=1,
            track_id=1,
            initial_rating=4,
            initial_likes_count=-1,
        )


def test_review_comment_like_update_and_soft_delete() -> None:
    review = ReviewComment(
        review_id=10,
        user_id=1,
        track_id=2,
        initial_rating=3,
        text="Decent track",
    )
    assert review.like() is review
    assert review.likes_count == 1
    review.like()
    assert review.likes_count == 2

    assert review.update_content(new_rating=4, new_text="Grew on me!") is review
    assert review.rating == 4
    assert review.text == "Grew on me!"

    with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
        review.update_content(new_rating=10, new_text="Too high")

    assert review.mark_as_deleted() is review
    assert review.is_deleted is True

    with pytest.raises(
        BusinessRuleViolationError, match="Cannot update a deleted review"
    ):
        review.update_content(new_rating=2, new_text="Should fail")
