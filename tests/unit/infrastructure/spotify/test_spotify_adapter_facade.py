"""Unit tests for the SpotifyAdapter facade."""

import pytest

from app.application.ports.services.music_service import (
    PlaylistExportPort,
    PlaylistSourcePort,
    TrackCatalogPort,
)
from app.application.ports.services.spotify import (
    SpotifyAuthPort,
    SpotifyPlaylistsPort,
    SpotifyQueuePort,
)
from app.domain.exceptions import SpotifyAuthError, SpotifyForbiddenError
from app.infrastructure.adapters.spotify import SpotifyCredentials
from app.infrastructure.adapters.spotify_adapter import SpotifyAdapter
from tests.utils.fakes import FakeResponse, FakeSession
from tests.utils.payloads import ALL_SCOPES, track_payload

REDIRECT = "http://127.0.0.1:8888/cb"
SPOTIFY_ID_A = "A" * 22
SPOTIFY_ID_B = "b" * 22


def _user_adapter(*responses: FakeResponse) -> tuple[SpotifyAdapter, FakeSession]:
    token = FakeResponse(
        200, {"access_token": "AT", "expires_in": 3600, "scope": ALL_SCOPES}
    )
    session = FakeSession(token, *responses)
    credentials = SpotifyCredentials(
        client_id="id", client_secret="s", redirect_uri=REDIRECT, refresh_token="RT"
    )
    return SpotifyAdapter(credentials, session), session


@pytest.mark.unit
class TestCapabilities:
    def test_satisfies_provider_ports(self) -> None:
        adapter = SpotifyAdapter()
        assert isinstance(adapter, TrackCatalogPort)
        assert isinstance(adapter, PlaylistExportPort)
        assert isinstance(adapter, PlaylistSourcePort)

    def test_modules_satisfy_spotify_ports(self) -> None:
        adapter, _ = _user_adapter()
        assert isinstance(adapter.auth, SpotifyAuthPort)
        assert isinstance(adapter.playlists, SpotifyPlaylistsPort)
        assert isinstance(adapter.player, SpotifyQueuePort)

    def test_client_credentials_exposes_only_auth_and_catalog(self) -> None:
        adapter = SpotifyAdapter(
            SpotifyCredentials(client_id="id", client_secret="s"),
            FakeSession(),
        )
        assert adapter.auth is not None
        assert adapter.catalog is not None
        assert (adapter.playlists, adapter.player) == (None, None)

    @pytest.mark.parametrize(
        "credentials",
        [
            SpotifyCredentials(
                client_id="id", client_secret="s", redirect_uri=REDIRECT
            ),
            SpotifyCredentials(client_id="id", redirect_uri=REDIRECT),
        ],
    )
    def test_user_flows_expose_all_modules(
        self, credentials: SpotifyCredentials
    ) -> None:
        adapter = SpotifyAdapter(credentials, FakeSession())
        assert adapter.playlists is not None
        assert adapter.player is not None


@pytest.mark.unit
class TestDisabled:
    @pytest.mark.parametrize(
        "call",
        [
            lambda adapter: adapter.search_tracks("daft punk"),
            lambda adapter: adapter.get_track("t1"),
            lambda adapter: adapter.get_playlist("p1"),
            lambda adapter: adapter.get_playlist_items("p1"),
            lambda adapter: adapter.export_playlist("acc", "Mix", []),
        ],
    )
    def test_operations_require_credentials(self, call) -> None:
        with pytest.raises(SpotifyAuthError, match="not configured"):
            call(SpotifyAdapter())

    def test_export_requires_a_user_token(self) -> None:
        adapter = SpotifyAdapter(
            SpotifyCredentials(client_id="id", client_secret="s"),
            FakeSession(),
        )
        with pytest.raises(SpotifyForbiddenError, match="user token"):
            adapter.export_playlist("acc", "Mix", [SPOTIFY_ID_A])


@pytest.mark.unit
class TestDelegation:
    def test_search_and_get_track(self) -> None:
        adapter, session = _user_adapter(
            FakeResponse(200, {"tracks": {"items": [track_payload("t1")]}}),
            FakeResponse(200, track_payload("t2")),
        )

        found = adapter.search_tracks("x", limit=2, offset=1, market="BR")
        track = adapter.get_track("t2", market="BR")

        assert found[0].external_id == "t1"
        assert track.external_id == "t2"
        assert session.calls[1]["params"]["market"] == "BR"

    def test_playlist_source_delegates(self) -> None:
        adapter, session = _user_adapter(
            FakeResponse(200, {"id": "p1", "name": "Mix"}),
            FakeResponse(200, {"items": [{"item": track_payload("t1")}], "total": 1}),
        )

        playlist = adapter.get_playlist("p1")
        page = adapter.get_playlist_items("p1", limit=10, offset=20)

        assert playlist.name == "Mix"
        assert [t.external_id for t in page.items] == ["t1"]
        assert page.total == 1
        assert page.raw_item_count == 1
        assert session.calls[2]["params"] == {"limit": 10, "offset": 20}


@pytest.mark.unit
class TestExportPlaylist:
    def test_creates_playlist_and_adds_only_spotify_tracks(self) -> None:
        adapter, session = _user_adapter(
            FakeResponse(201, {"id": "new", "name": "Mix"}),
            FakeResponse(201, {"snapshot_id": "s"}),
        )

        playlist_id = adapter.export_playlist(
            "acc", "Mix", [SPOTIFY_ID_A, "42", SPOTIFY_ID_B]
        )

        assert playlist_id == "new"
        create, add = session.calls[1], session.calls[2]
        assert create["json"]["name"] == "Mix"
        assert add["url"].endswith("/playlists/new/items")
        assert add["json"] == {
            "uris": [f"spotify:track:{SPOTIFY_ID_A}", f"spotify:track:{SPOTIFY_ID_B}"]
        }

    def test_batches_items_in_groups_of_one_hundred(self) -> None:
        ids = [f"{i:022d}" for i in range(150)]
        adapter, session = _user_adapter(
            FakeResponse(201, {"id": "new", "name": "Mix"}),
            FakeResponse(201, {"snapshot_id": "s1"}),
            FakeResponse(201, {"snapshot_id": "s2"}),
        )

        adapter.export_playlist("acc", "Mix", ids)

        sizes = [len(call["json"]["uris"]) for call in session.calls[2:]]
        assert sizes == [100, 50]

    def test_without_spotify_tracks_creates_empty_playlist(self) -> None:
        adapter, session = _user_adapter(
            FakeResponse(201, {"id": "new", "name": "Mix"})
        )

        assert adapter.export_playlist("acc", "Mix", ["1", "2"]) == "new"
        assert len(session.calls) == 2
