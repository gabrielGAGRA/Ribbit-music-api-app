"""Unit tests for recommendation scoring, soft-delete safety, Spotify sync, and access history."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.application.dtos.review_dtos import SearchTracksCommand
from app.application.dtos.spotify_dtos import SyncPlaylistFromSpotifyCommand
from app.application.ports.services.music_service import (
    CatalogTrack,
    PlaylistItemsPage,
    ProviderPlaylist,
)
from app.application.use_cases.discovery.get_next_discovery_track import (
    GetNextDiscoveryTrackUseCase,
)
from app.application.use_cases.review.like_review_comment import (
    LikeReviewCommentUseCase,
)
from app.application.use_cases.review.search_tracks import SearchTracksUseCase
from app.application.use_cases.spotify.helpers import upsert_catalog_track
from app.application.use_cases.spotify.sync_playlist_from_spotify import (
    SyncPlaylistFromSpotifyUseCase,
)
from app.application.use_cases.user.list_user_access_history import (
    ListUserAccessHistoryUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.review import ReviewComment
from app.domain.models.track import Track
from app.domain.models.track_access import TrackAccessEntry
from app.domain.models.user import User
from app.domain.services.recommendation import (
    RecommendationProfile,
    score_track_for_user,
)
lazy from app.domain.models.playlist import Playlist


def _make_user(
    *,
    age: int = 25,
    favorite_genres: tuple[str, ...] = (),
    blocked_genres: tuple[str, ...] = (),
) -> User:
    return User(
        user_id=1,
        email="user@example.com",
        password_hash="hashed",
        display_name="Listener",
        age=age,
        plan_id=1,
        favorite_genres=frozenset(favorite_genres),
        blocked_genres=frozenset(blocked_genres),
    )


def _make_track(
    track_id: int,
    *,
    title: str = "Song",
    artist: str = "Artist",
    genre: str = "Pop",
    release_year: int | None = 2020,
    average_rating: float | None = None,
    explicit: bool = False,
    is_deleted: bool = False,
    spotify_id: str | None = None,
) -> Track:
    return Track(
        track_id=track_id,
        title=title,
        artist=artist,
        duration_seconds=180,
        genre=genre,
        release_year=release_year,
        average_rating=average_rating,
        explicit=explicit,
        is_deleted=is_deleted,
        spotify_id=spotify_id,
    )


def test_score_track_for_user_combines_profile_ratings_and_blocks() -> None:
    user = _make_user(favorite_genres=("Rock",), blocked_genres=("Metal",))
    profile = RecommendationProfile(
        positive_genres={"jazz": 2.0},
        disliked_genres={"country": 2.0},
        positive_artists={"miles": 2.0},
        disliked_artists={"bad artist": 2.0},
        positive_decades={1990: 2.0},
    )

    fav_high_rated = _make_track(
        1, genre="Rock", artist="Queen", release_year=1992, average_rating=4.8
    )
    history_match = _make_track(
        2, genre="Jazz", artist="Miles", release_year=1995, average_rating=4.0
    )
    disliked = _make_track(
        3, genre="Country", artist="Bad Artist", release_year=2022, average_rating=2.0
    )
    blocked = _make_track(4, genre="Metal", artist="Metallica")

    assert score_track_for_user(
        fav_high_rated, user, profile=profile
    ) > score_track_for_user(history_match, user, profile=profile)
    assert score_track_for_user(
        history_match, user, profile=profile
    ) > score_track_for_user(disliked, user, profile=profile)
    assert score_track_for_user(blocked, user, profile=profile) == 0.0


def test_get_next_discovery_track_builds_profile_from_interactions_and_access() -> None:
    user = _make_user(favorite_genres=("Jazz",))
    liked_track = _make_track(10, genre="Jazz", artist="Coltrane", release_year=1965)
    disliked_track = _make_track(
        11, genre="Country", artist="Skipper", release_year=2020
    )
    accessed_track = _make_track(12, genre="Jazz", artist="Coltrane", release_year=1968)
    candidate_jazz = _make_track(
        20, genre="Jazz", artist="Coltrane", release_year=1964, average_rating=4.9
    )

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock()
    track_repo.list_active.return_value = [candidate_jazz]
    track_repo.find_by_ids.return_value = {
        10: liked_track,
        11: disliked_track,
        12: accessed_track,
    }

    interaction_repo = MagicMock()
    interaction_repo.list_interacted_track_ids.return_value = [10, 11]
    interaction_repo.list_by_user.return_value = [
        Interaction(user_id=1, track_id=10, action=InteractionAction.SUPERLIKE),
        Interaction(user_id=1, track_id=11, action=InteractionAction.DISLIKE),
    ]

    track_access_repo = MagicMock()
    track_access_repo.list_by_user.return_value = [
        TrackAccessEntry(
            access_id=1,
            user_id=1,
            track_id=12,
            track_title="Accessed",
            track_artist="Coltrane",
            track_genre="Jazz",
            source="play",
            accessed_at=datetime.now(UTC),
        )
    ]

    uc = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
        track_access_repo=track_access_repo,
    )
    chosen = uc.execute(1)
    assert chosen is candidate_jazz
    track_access_repo.list_by_user.assert_called_once()


def test_search_tracks_skips_soft_deleted_spotify_fallback_tracks() -> None:
    user = _make_user(age=25)
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user

    deleted_existing = _make_track(
        99, title="Deleted Song", artist="Artist", spotify_id="sp-del", is_deleted=True
    )
    track_repo = MagicMock()
    track_repo.find_by_filters.return_value = []
    track_repo.find_by_spotify_id.return_value = deleted_existing

    music_service = MagicMock()
    music_service.search_tracks.return_value = [
        CatalogTrack(
            external_id="sp-del",
            title="Deleted Song",
            artist="Artist",
            album=None,
            duration_ms=180000,
            preview_url=None,
            explicit=False,
        )
    ]

    uc = SearchTracksUseCase(
        user_repo=user_repo, track_repo=track_repo, music_service=music_service
    )
    results = uc.execute(SearchTracksCommand(user_id=1, query="Deleted Song"))
    assert results == []
    track_repo.save.assert_not_called()


def test_like_review_comment_rejects_deleted_track() -> None:
    review_repo = MagicMock()
    review_repo.find_by_id.return_value = ReviewComment(
        review_id=5, user_id=1, track_id=77, initial_rating=5, text="Great"
    )
    track_repo = MagicMock()
    track_repo.find_by_id.return_value = _make_track(77, is_deleted=True)

    uc = LikeReviewCommentUseCase(review_repo=review_repo, track_repo=track_repo)
    with pytest.raises(EntityNotFoundError):
        uc.execute(review_id=5, user_id=1)


def test_upsert_and_sync_playlist_preserve_explicit_and_filter_minor_and_deleted() -> (
    None
):
    minor = _make_user(age=15)
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = minor

    saved_tracks: dict[str, Track] = {}

    def _find_by_spotify_id(sp_id: str) -> Track | None:
        return saved_tracks.get(sp_id)

    def _save_track(track: Track) -> Track:
        if track.track_id is None:
            track.track_id = len(saved_tracks) + 1
        if track.spotify_id:
            saved_tracks[track.spotify_id] = track
        return track

    saved_tracks["sp-deleted"] = _make_track(
        50, spotify_id="sp-deleted", is_deleted=True
    )

    track_repo = MagicMock()
    track_repo.find_by_spotify_id.side_effect = _find_by_spotify_id
    track_repo.save.side_effect = _save_track

    playlist_repo = MagicMock()
    playlist_repo.list_by_user.return_value = []
    playlist_repo.save.side_effect = lambda p: p

    source = MagicMock()
    source.get_playlist.return_value = ProviderPlaylist(
        external_id="pl-1", name="Imported", description=None
    )
    source.get_playlist_items.return_value = PlaylistItemsPage(
        items=[
            CatalogTrack(
                external_id="sp-clean",
                title="Clean",
                artist="A",
                album=None,
                duration_ms=120000,
                preview_url=None,
                explicit=False,
            ),
            CatalogTrack(
                external_id="sp-explicit",
                title="Explicit",
                artist="B",
                album=None,
                duration_ms=120000,
                preview_url=None,
                explicit=True,
            ),
            CatalogTrack(
                external_id="sp-deleted",
                title="Deleted",
                artist="C",
                album=None,
                duration_ms=120000,
                preview_url=None,
                explicit=False,
            ),
        ],
        raw_item_count=3,
        total=3,
    )

    uc = SyncPlaylistFromSpotifyUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
        source=source,
    )
    playlist: Playlist = uc.execute(
        SyncPlaylistFromSpotifyCommand(
            user_id=1, spotify_playlist_id="pl-1", genre="Pop"
        )
    )
    assert [t.title for t in playlist.tracks] == ["Clean"]
    assert saved_tracks["sp-explicit"].explicit is True

    # Also verify upsert_catalog_track preserves explicit on existing track
    existing = upsert_catalog_track(
        track_repo,
        CatalogTrack(
            external_id="sp-explicit",
            title="Explicit",
            artist="B",
            album=None,
            duration_ms=120000,
            preview_url=None,
            explicit=True,
        ),
        "Pop",
    )
    assert existing is not None and existing.explicit is True


def test_list_user_access_history_adult_keeps_seen_ids() -> None:
    adult = _make_user(age=25)
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = adult

    explicit_track = _make_track(9, explicit=True)
    track_repo = MagicMock()
    track_repo.find_by_id.return_value = explicit_track

    access_repo = MagicMock()
    access_repo.list_by_user.return_value = [
        TrackAccessEntry(
            access_id=1,
            user_id=1,
            track_id=9,
            track_title="Explicit",
            track_artist="Artist",
            track_genre="Pop",
            track_explicit=True,
            source="play",
            accessed_at=datetime.now(UTC),
        )
    ]
    access_repo.list_seen_track_ids.return_value = [9]

    uc = ListUserAccessHistoryUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        track_access_repo=access_repo,
    )
    res = uc.execute(user_id=1)
    assert res.seen_track_ids == [9]
    assert len(res.items) == 1
