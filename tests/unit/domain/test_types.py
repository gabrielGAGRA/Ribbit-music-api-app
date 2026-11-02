"""Tests for domain type aliases and semantic identifiers."""

from app.domain.models.track import ExternalTrackId, TrackId


def test_track_id_is_new_type() -> None:
    tid = TrackId(42)
    assert tid == 42
    assert isinstance(tid, int)


def test_external_track_id_is_new_type() -> None:
    ext_id = ExternalTrackId("spotify:track:12345")
    assert ext_id == "spotify:track:12345"
    assert isinstance(ext_id, str)
