"""Unit tests for Spotify catalog, playlists and player modules."""

import pytest

from app.domain.exceptions import SpotifyError
from app.infrastructure.adapters.spotify.catalog import SpotifyCatalog
from app.infrastructure.adapters.spotify.player import SpotifyPlayer
from app.infrastructure.adapters.spotify.playlists import SpotifyPlaylists
from tests.utils.fakes import FakeResponse
from tests.utils.payloads import track_payload


@pytest.mark.unit
class TestCatalog:
    def test_search_maps_tracks_and_sends_params(self, make_http) -> None:
        http, session = make_http(
            FakeResponse(200, {"tracks": {"items": [track_payload()]}})
        )

        tracks = SpotifyCatalog(http).search_tracks("daft punk", limit=3, offset=6)

        call = session.calls[1]
        assert call["url"].endswith("/search")
        assert call["params"] == {
            "q": "daft punk",
            "type": "track",
            "limit": 3,
            "offset": 6,
        }
        track = tracks[0]
        assert (track.external_id, track.artist, track.album) == ("t1", "A, B", "Album")
        assert track.uri == "spotify:track:t1"
        assert track.duration_ms == 180_400
        assert track.cover_url == "http://img/large"
        assert track.release_year == 2019

    @pytest.mark.parametrize("limit", [0, 11])
    def test_search_limit_is_bounded_by_development_mode(
        self, make_http, limit: int
    ) -> None:
        http, _ = make_http()
        with pytest.raises(ValueError, match="limit"):
            SpotifyCatalog(http).search_tracks("x", limit=limit)

    def test_search_without_tracks_key_is_empty(self, make_http) -> None:
        http, _ = make_http(FakeResponse(200, {}))
        assert SpotifyCatalog(http).search_tracks("x") == []

    def test_get_track_uses_single_item_route(self, make_http) -> None:
        http, session = make_http(FakeResponse(200, track_payload("abc")))

        track = SpotifyCatalog(http).get_track("abc")

        assert session.calls[1]["url"].endswith("/tracks/abc")
        assert track.uri == "spotify:track:abc"

    def test_track_without_release_date_or_images(self, make_http) -> None:
        payload = track_payload()
        payload["album"] = {"name": "Album"}
        http, _ = make_http(FakeResponse(200, payload))

        track = SpotifyCatalog(http).get_track("t1")

        assert (track.cover_url, track.release_year) == (None, None)

    @pytest.mark.parametrize("payload", [{"id": "x"}, {"id": "x", "artists": 1}])
    def test_malformed_payload_is_mapped(self, make_http, payload) -> None:
        http, _ = make_http(FakeResponse(200, {"tracks": {"items": [payload]}}))
        with pytest.raises(SpotifyError, match="unexpected"):
            SpotifyCatalog(http).search_tracks("x")


@pytest.mark.unit
class TestPlaylists:
    def test_get_my_playlists(self, make_http) -> None:
        http, session = make_http(
            FakeResponse(
                200,
                {
                    "items": [
                        {"id": "p1", "name": "Mix", "snapshot_id": "s", "public": True}
                    ]
                },
            )
        )

        playlists = SpotifyPlaylists(http).get_my_playlists(limit=5)

        assert session.calls[1]["url"].endswith("/me/playlists")
        assert playlists[0].external_id == "p1"
        assert playlists[0].snapshot_id == "s"

    def test_get_playlist(self, make_http) -> None:
        http, session = make_http(FakeResponse(200, {"id": "p1", "name": "Mix"}))

        playlist = SpotifyPlaylists(http).get_playlist("p1")

        assert session.calls[1]["url"].endswith("/playlists/p1")
        assert (playlist.external_id, playlist.name) == ("p1", "Mix")

    def test_malformed_playlist_is_mapped(self, make_http) -> None:
        http, _ = make_http(FakeResponse(200, {"id": "p1"}))
        with pytest.raises(SpotifyError, match="playlist payload"):
            SpotifyPlaylists(http).get_playlist("p1")

    def test_create_playlist_posts_body(self, make_http) -> None:
        http, session = make_http(FakeResponse(201, {"id": "p9", "name": "New"}))

        created = SpotifyPlaylists(http).create_playlist("New", description="d")

        call = session.calls[1]
        assert call["method"] == "POST"
        assert call["url"].endswith("/me/playlists")
        assert call["json"] == {
            "name": "New",
            "public": False,
            "collaborative": False,
            "description": "d",
        }
        assert created.external_id == "p9"

    def test_update_details_sends_only_given_fields(self, make_http) -> None:
        http, session = make_http(FakeResponse(200))

        SpotifyPlaylists(http).update_playlist_details("p1", name="Renamed")

        call = session.calls[1]
        assert (call["method"], call["json"]) == ("PUT", {"name": "Renamed"})

    def test_get_playlist_items_reads_item_key_and_skips_non_tracks(
        self, make_http
    ) -> None:
        payload = {
            "items": [
                {"item": track_payload("t1")},
                {"item": None},
                {"item": {"type": "episode", "id": "e1"}},
            ]
        }
        http, session = make_http(FakeResponse(200, payload))

        page = SpotifyPlaylists(http).get_playlist_items("p1", limit=50, offset=0)

        assert session.calls[1]["url"].endswith("/playlists/p1/items")
        assert [t.external_id for t in page.items] == ["t1"]
        assert page.raw_item_count == 3

    def test_add_items_returns_snapshot(self, make_http) -> None:
        http, session = make_http(FakeResponse(201, {"snapshot_id": "snap"}))

        snapshot = SpotifyPlaylists(http).add_playlist_items(
            "p1", ["spotify:track:a"], position=0
        )

        assert snapshot == "snap"
        assert session.calls[1]["json"] == {"uris": ["spotify:track:a"], "position": 0}

    def test_response_without_snapshot_is_mapped(self, make_http) -> None:
        http, _ = make_http(FakeResponse(201, {}))
        with pytest.raises(SpotifyError, match="snapshot_id"):
            SpotifyPlaylists(http).add_playlist_items("p1", ["spotify:track:a"])

    def test_remove_items_body_shape(self, make_http) -> None:
        http, session = make_http(FakeResponse(200, {"snapshot_id": "s2"}))

        SpotifyPlaylists(http).remove_playlist_items(
            "p1", ["spotify:track:a"], snapshot_id="s1"
        )

        call = session.calls[1]
        assert call["method"] == "DELETE"
        assert call["json"] == {
            "items": [{"uri": "spotify:track:a"}],
            "snapshot_id": "s1",
        }

    def test_update_items_reorder_body(self, make_http) -> None:
        http, session = make_http(FakeResponse(200, {"snapshot_id": "s3"}))

        result = SpotifyPlaylists(http).update_playlist_items(
            "p1", range_start=0, insert_before=3
        )

        assert result == "s3"
        assert session.calls[1]["json"] == {"range_start": 0, "insert_before": 3}

    def test_update_items_replace_all_without_snapshot_returns_none(
        self, make_http
    ) -> None:
        http, session = make_http(FakeResponse(200))

        result = SpotifyPlaylists(http).update_playlist_items(
            "p1", uris=["spotify:track:a"]
        )

        assert result is None
        assert session.calls[1]["json"] == {"uris": ["spotify:track:a"]}

    def test_cover_get_and_upload(self, make_http) -> None:
        http, session = make_http(
            FakeResponse(200, [{"url": "http://c"}]), FakeResponse(202)
        )
        playlists = SpotifyPlaylists(http)

        assert playlists.get_playlist_cover("p1") == ["http://c"]
        playlists.upload_playlist_cover("p1", "B64")

        upload = session.calls[2]
        assert (upload["method"], upload["data"]) == ("PUT", "B64")
        assert upload["headers"]["Content-Type"] == "image/jpeg"


@pytest.mark.unit
class TestPlayer:
    def test_get_queue(self, make_http) -> None:
        http, session = make_http(
            FakeResponse(
                200,
                {
                    "currently_playing": track_payload("c"),
                    "queue": [track_payload("q1"), {"type": "episode", "id": "e"}],
                },
            )
        )

        queue = SpotifyPlayer(http).get_queue()

        assert session.calls[1]["url"].endswith("/me/player/queue")
        assert queue.currently_playing is not None
        assert [t.external_id for t in queue.queue] == ["q1"]

    def test_get_queue_when_empty(self, make_http) -> None:
        http, _ = make_http(FakeResponse(204))

        queue = SpotifyPlayer(http).get_queue()

        assert (queue.currently_playing, queue.queue) == (None, ())

    def test_add_to_queue_uses_query_params(self, make_http) -> None:
        http, session = make_http(FakeResponse(204))

        SpotifyPlayer(http).add_to_queue("spotify:track:a", device_id="d1")

        call = session.calls[1]
        assert call["method"] == "POST"
        assert call["url"].endswith("/me/player/queue")
        assert call["params"] == {"uri": "spotify:track:a", "device_id": "d1"}

    @pytest.mark.parametrize(
        ("method_name", "http_method", "suffix"),
        [
            ("next_track", "POST", "/me/player/next"),
            ("previous_track", "POST", "/me/player/previous"),
            ("pause", "PUT", "/me/player/pause"),
        ],
    )
    def test_simple_controls(
        self, make_http, method_name: str, http_method: str, suffix: str
    ) -> None:
        http, session = make_http(FakeResponse(204))

        getattr(SpotifyPlayer(http), method_name)()

        call = session.calls[1]
        assert call["method"] == http_method
        assert call["url"].endswith(suffix)

    def test_seek(self, make_http) -> None:
        http, session = make_http(FakeResponse(204))

        SpotifyPlayer(http).seek(42_000)

        assert session.calls[1]["params"] == {"position_ms": 42_000}

    def test_play_builds_body_from_given_fields_only(self, make_http) -> None:
        http, session = make_http(FakeResponse(204))

        SpotifyPlayer(http).play(context_uri="spotify:playlist:p", offset=2)

        call = session.calls[1]
        assert call["method"] == "PUT"
        assert call["json"] == {
            "context_uri": "spotify:playlist:p",
            "offset": {"position": 2},
        }

    def test_play_without_arguments_resumes_without_body(self, make_http) -> None:
        http, session = make_http(FakeResponse(204))

        SpotifyPlayer(http).play()

        assert "json" not in session.calls[1]

    def test_playback_state_none_when_inactive(self, make_http) -> None:
        http, _ = make_http(FakeResponse(204))
        assert SpotifyPlayer(http).get_playback_state() is None

    def test_playback_state_mapped(self, make_http) -> None:
        http, _ = make_http(
            FakeResponse(
                200,
                {
                    "is_playing": True,
                    "progress_ms": 1000,
                    "device": {"id": "d1", "name": "Phone"},
                    "item": track_payload("t1"),
                },
            )
        )

        state = SpotifyPlayer(http).get_playback_state()

        assert state is not None
        assert state.track is not None
        assert (state.is_playing, state.device_id, state.track.external_id) == (
            True,
            "d1",
            "t1",
        )

    def test_playback_state_without_is_playing_is_mapped(self, make_http) -> None:
        http, _ = make_http(FakeResponse(200, {"progress_ms": 1}))
        with pytest.raises(SpotifyError, match="playback payload"):
            SpotifyPlayer(http).get_playback_state()
