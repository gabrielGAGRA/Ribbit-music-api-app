"""Unit tests for Track, Playlist, and Interaction domain models."""

from datetime import UTC, datetime

import pytest

from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models import Interaction, InteractionAction, Playlist, Track


def test_track_construction_and_defaults() -> None:
    now = datetime.now(tz=UTC)
    track = Track(
        track_id=101,
        title="Ribbit Symphony",
        artist="Frog Choir",
        duration_seconds=215,
        genre="Ambient",
        spotify_id="sp_101",
        album="Pond Life",
        country="BR",
        release_year=2025,
        cover_url="https://example.com/cover.jpg",
        itunes_preview_url="https://example.com/preview.m4a",
        explicit=False,
        is_deleted=False,
        created_at=now,
    )
    assert track.track_id == 101
    assert track.title == "Ribbit Symphony"
    assert track.artist == "Frog Choir"
    assert track.duration_seconds == 215
    assert track.genre == "Ambient"
    assert track.spotify_id == "sp_101"
    assert track.album == "Pond Life"
    assert track.country == "BR"
    assert track.release_year == 2025
    assert track.cover_url == "https://example.com/cover.jpg"
    assert track.itunes_preview_url == "https://example.com/preview.m4a"
    assert track.explicit is False
    assert track.is_deleted is False
    assert track.created_at == now


def test_track_duration_validation() -> None:
    with pytest.raises(ValueError, match="Track duration must be positive"):
        Track(
            title="Zero Track",
            artist="Artist",
            duration_seconds=0,
            genre="Pop",
        )

    with pytest.raises(ValueError, match="Track duration must be positive"):
        Track(
            title="Negative Track",
            artist="Artist",
            duration_seconds=-10,
            genre="Pop",
        )


def test_track_state_transitions_explicit_and_soft_delete() -> None:
    track = Track(
        track_id=1,
        title="Song",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    assert track.set_explicit(True) is track
    assert track.explicit is True
    assert track.set_explicit(False) is track
    assert track.explicit is False

    assert track.mark_as_deleted() is track
    assert track.is_deleted is True
    assert track.restore() is track
    assert track.is_deleted is False


def test_interaction_action_enum_values_and_is_positive() -> None:
    assert InteractionAction.LIKE == "like"
    assert InteractionAction.SUPERLIKE == "superlike"
    assert InteractionAction.DISLIKE == "dislike"

    assert InteractionAction.LIKE.is_positive is True
    assert InteractionAction.SUPERLIKE.is_positive is True
    assert InteractionAction.DISLIKE.is_positive is False


def test_interaction_construction_and_action_transitions() -> None:
    now = datetime.now(tz=UTC)
    interaction = Interaction(
        interaction_id=7,
        user_id=1,
        track_id=50,
        action=InteractionAction.DISLIKE,
        created_at=now,
    )
    assert interaction.interaction_id == 7
    assert interaction.user_id == 1
    assert interaction.track_id == 50
    assert interaction.action is InteractionAction.DISLIKE
    assert interaction.is_positive is False
    assert interaction.created_at == now

    assert interaction.change_action(InteractionAction.SUPERLIKE) is interaction
    assert interaction.action is InteractionAction.SUPERLIKE
    assert interaction.is_positive is True

    interaction.change_action(InteractionAction.LIKE)
    assert interaction.action is InteractionAction.LIKE
    assert interaction.is_positive is True


def test_playlist_construction_ownership_and_immutable_tracks_view() -> None:
    t1 = Track(track_id=1, title="T1", artist="A1", duration_seconds=100, genre="Pop")
    t2 = Track(track_id=2, title="T2", artist="A2", duration_seconds=150, genre="Pop")

    playlist = Playlist(
        playlist_id=10,
        user_id=42,
        name="My Favorites",
        description="Best tracks",
        initial_tracks=[t1, t2],
    )
    assert playlist.playlist_id == 10
    assert playlist.user_id == 42
    assert playlist.name == "My Favorites"
    assert playlist.description == "Best tracks"
    assert playlist.is_exported is False
    assert playlist.spotify_playlist_id is None
    assert playlist.is_owned_by(42) is True
    assert playlist.is_owned_by(99) is False
    assert isinstance(playlist.tracks, tuple)
    assert playlist.tracks == (t1, t2)


def test_playlist_add_remove_and_duplicate_track_prevention() -> None:
    t1 = Track(track_id=1, title="T1", artist="A1", duration_seconds=100, genre="Pop")
    t2 = Track(
        track_id=1, title="T1 Dup", artist="A1", duration_seconds=100, genre="Pop"
    )
    unpersisted_a = Track(
        track_id=None, title="New A", artist="A", duration_seconds=120, genre="Pop"
    )
    unpersisted_b = Track(
        track_id=None, title="New B", artist="B", duration_seconds=130, genre="Pop"
    )

    playlist = Playlist(user_id=1, name="Mix")
    assert playlist.add_track(t1) is playlist
    assert playlist.add_track(unpersisted_a) is playlist
    assert playlist.add_track(unpersisted_b) is playlist
    assert len(playlist.tracks) == 3

    with pytest.raises(
        BusinessRuleViolationError, match="Track 1 is already in the playlist"
    ):
        playlist.add_track(t2)

    assert playlist.remove_track(1) is playlist
    assert playlist.tracks == (unpersisted_a, unpersisted_b)


def test_playlist_export_sets_spotify_id_and_flag() -> None:
    playlist = Playlist(playlist_id=5, user_id=1, name="Roadtrip")
    assert playlist.export("spotify_pl_abc") is playlist
    assert playlist.is_exported is True
    assert playlist.spotify_playlist_id == "spotify_pl_abc"


def test_track_refresh_catalog_metadata_keeps_curated_fields() -> None:
    track = Track(
        track_id=1,
        title="Old",
        artist="Old",
        duration_seconds=10,
        genre="Rock",
        explicit=True,
    )

    result = track.refresh_catalog_metadata(
        title="New",
        artist="Artist",
        duration_seconds=200,
        album="Album",
        cover_url="http://c",
        release_year=2020,
    )

    assert result is track
    assert (track.title, track.artist, track.duration_seconds) == ("New", "Artist", 200)
    assert (track.album, track.cover_url, track.release_year) == (
        "Album",
        "http://c",
        2020,
    )
    assert (track.genre, track.explicit, track.track_id) == ("Rock", True, 1)


def test_track_refresh_catalog_metadata_rejects_non_positive_duration() -> None:
    track = Track(title="T", artist="A", duration_seconds=10, genre="Rock")

    with pytest.raises(ValueError, match="duration"):
        track.refresh_catalog_metadata(
            title="T",
            artist="A",
            duration_seconds=0,
            album=None,
            cover_url=None,
            release_year=None,
        )

    assert track.duration_seconds == 10


def test_playlist_replace_tracks_swaps_whole_list() -> None:
    old = Track(track_id=1, title="Old", artist="A", duration_seconds=10, genre="Rock")
    new = Track(track_id=2, title="New", artist="A", duration_seconds=20, genre="Rock")
    playlist = Playlist(user_id=1, name="Mix", initial_tracks=[old])

    assert playlist.replace_tracks([new]) is playlist

    assert playlist.tracks == (new,)


def test_playlist_replace_tracks_keeps_previous_tracks_on_rejection() -> None:
    old = Track(track_id=1, title="Old", artist="A", duration_seconds=10, genre="Rock")
    long_track = Track(
        track_id=2, title="Long", artist="A", duration_seconds=100, genre="Rock"
    )
    playlist = Playlist(
        user_id=1, name="Mix", max_duration_seconds=50, initial_tracks=[old]
    )

    with pytest.raises(BusinessRuleViolationError):
        playlist.replace_tracks([long_track])

    assert playlist.tracks == (old,)
