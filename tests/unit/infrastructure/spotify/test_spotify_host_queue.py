"""Unit tests for SpotifyHostQueueAdapter."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.domain.exceptions import SpotifyPremiumRequiredError
from app.domain.models.user import User
from app.infrastructure.adapters.spotify.credentials import SpotifyCredentials
from app.infrastructure.adapters.spotify.host_queue import SpotifyHostQueueAdapter


def _make_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    resp.content = b"{}" if json_body is not None else b""
    resp.json.return_value = json_body
    return resp


def _make_owner(
    *,
    access_token: str | None = "acc_valid",  # noqa: S107
    refresh_token: str | None = "ref_tok",  # noqa: S107
    expires_delta: timedelta = timedelta(minutes=30),
) -> User:
    return User(
        user_id=1,
        email="owner@example.com",
        password_hash="pw",
        display_name="Owner",
        plan_id=1,
        spotify_id="sp_owner",
        spotify_premium=True,
        spotify_access_token=access_token,
        spotify_refresh_token=refresh_token,
        spotify_token_expires_at=datetime.now(UTC) + expires_delta,
    )


def test_enqueue_track_uses_seeded_token_and_calls_queue_endpoint() -> None:
    session = MagicMock()
    session.request.return_value = _make_response(204)
    adapter = SpotifyHostQueueAdapter(
        credentials=SpotifyCredentials(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://127.0.0.1:8888/callback",
        ),
        session=session,
    )

    adapter.enqueue_track(_make_owner(), "spotify:track:abc123")

    session.request.assert_called_once()
    call_args, call_kwargs = session.request.call_args
    assert call_args == ("POST", "https://api.spotify.com/v1/me/player/queue")
    assert call_kwargs["params"] == {"uri": "spotify:track:abc123"}
    assert call_kwargs["headers"]["Authorization"] == "Bearer acc_valid"


def test_skip_to_next_and_start_track_call_player_endpoints() -> None:
    session = MagicMock()
    session.request.return_value = _make_response(204)
    adapter = SpotifyHostQueueAdapter(
        credentials=SpotifyCredentials(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://127.0.0.1:8888/callback",
        ),
        session=session,
    )
    owner = _make_owner()

    adapter.skip_to_next(owner)
    adapter.start_track(owner, "spotify:track:xyz789")

    assert session.request.call_count == 2
    first_args, _ = session.request.call_args_list[0]
    second_args, second_kwargs = session.request.call_args_list[1]
    assert first_args == ("POST", "https://api.spotify.com/v1/me/player/next")
    assert second_args == ("PUT", "https://api.spotify.com/v1/me/player/play")
    assert second_kwargs["json"] == {"uris": ["spotify:track:xyz789"]}


def test_expired_token_refreshes_and_403_premium_required_propagates() -> None:
    session = MagicMock()
    session.request.side_effect = [
        _make_response(
            200,
            {
                "access_token": "acc_refreshed",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        ),
        _make_response(
            403,
            {
                "error": {
                    "status": 403,
                    "message": "Player command failed: Premium required",
                    "reason": "PREMIUM_REQUIRED",
                }
            },
        ),
    ]
    adapter = SpotifyHostQueueAdapter(
        credentials=SpotifyCredentials(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://127.0.0.1:8888/callback",
        ),
        session=session,
    )
    owner = _make_owner(access_token="expired", expires_delta=timedelta(minutes=-5))

    with pytest.raises(SpotifyPremiumRequiredError):
        adapter.enqueue_track(owner, "spotify:track:abc123")

    assert session.request.call_args_list[0][0] == (
        "POST",
        "https://accounts.spotify.com/api/token",
    )
    assert session.request.call_args_list[1][1]["headers"]["Authorization"] == (
        "Bearer acc_refreshed"
    )
