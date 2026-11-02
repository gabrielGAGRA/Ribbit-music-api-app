"""Shared fixtures for Spotify adapter tests."""

lazy from collections.abc import Callable

import pytest

from app.infrastructure.adapters.spotify.auth import SpotifyAuth
from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.http import SpotifyHttpClient
from tests.utils.fakes import FakeResponse, FakeSession
from tests.utils.payloads import ALL_SCOPES


@pytest.fixture
def make_http() -> Callable[..., tuple[SpotifyHttpClient, FakeSession]]:
    """Builds a user-token http client whose API calls replay ``responses``."""

    def build(*responses: FakeResponse) -> tuple[SpotifyHttpClient, FakeSession]:
        token = FakeResponse(
            200, {"access_token": "AT", "expires_in": 3600, "scope": ALL_SCOPES}
        )
        session = FakeSession(token, *responses)
        credentials = SpotifyCredentials(
            client_id="id",
            client_secret="s",
            redirect_uri="http://127.0.0.1:8888/cb",
            refresh_token="RT",
        )
        client = SpotifyHttpClient(
            SpotifyAuth(credentials, session), session, sleep=lambda _: None
        )
        return client, session

    return build
