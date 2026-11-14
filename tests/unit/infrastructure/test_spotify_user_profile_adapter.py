"""Unit tests for Spotify user profile adapter."""

from unittest.mock import MagicMock

import niquests
import pytest

from app.domain.exceptions import SpotifyAuthError
from app.infrastructure.adapters.spotify.user_profile import SpotifyUserProfileAdapter


def test_get_current_user_profile_successful() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "spotify_user_99",
        "display_name": "Spotify Tester",
        "email": "spotify_user@example.com",
        "product": "premium",
    }
    mock_session.get.return_value = mock_response

    adapter = SpotifyUserProfileAdapter(session=mock_session)
    profile = adapter.get_current_user_profile("valid_token")

    assert profile.id == "spotify_user_99"
    assert profile.display_name == "Spotify Tester"
    assert profile.email == "spotify_user@example.com"
    assert profile.product == "premium"
    assert profile.is_premium is True


def test_get_current_user_profile_free_or_missing_product_is_not_premium() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "spotify_free_1",
        "display_name": "Free User",
        "product": "free",
    }
    mock_session.get.return_value = mock_response

    adapter = SpotifyUserProfileAdapter(session=mock_session)
    assert adapter.get_current_user_profile("tok").is_premium is False

    mock_response.json.return_value = {"id": "spotify_open_1"}
    assert adapter.get_current_user_profile("tok").is_premium is False


def test_get_current_user_profile_blank_token_raises_error() -> None:
    adapter = SpotifyUserProfileAdapter()
    with pytest.raises(SpotifyAuthError, match="cannot be blank"):
        adapter.get_current_user_profile("  ")


def test_get_current_user_profile_error_status_raises_error() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_session.get.return_value = mock_response

    adapter = SpotifyUserProfileAdapter(session=mock_session)
    with pytest.raises(SpotifyAuthError, match="status 401"):
        adapter.get_current_user_profile("expired_token")
