"""Unit tests for Spotify OAuth connect use cases."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.spotify_dtos import SpotifyTokens
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.spotify import (
    SpotifyAuthPort,
    SpotifyUserProfile,
    SpotifyUserProfilePort,
)
from app.application.use_cases.spotify.connect_spotify_account import (
    ConnectSpotifyAccountUseCase,
)
from app.application.use_cases.spotify.get_spotify_authorize_url import (
    GetSpotifyAuthorizeUrlUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models.user import User


def test_get_spotify_authorize_url_calls_auth_port() -> None:
    mock_auth = MagicMock(spec=SpotifyAuthPort)
    mock_auth.get_authorize_url.return_value = (
        "https://accounts.spotify.com/authorize?url=test"
    )

    use_case = GetSpotifyAuthorizeUrlUseCase(spotify_auth=mock_auth)
    url = use_case.execute(state="random_state")

    assert url == "https://accounts.spotify.com/authorize?url=test"
    mock_auth.get_authorize_url.assert_called_once()
    called_scopes, called_state = mock_auth.get_authorize_url.call_args[0]
    assert "user-read-private" in called_scopes
    assert "user-modify-playback-state" in called_scopes
    assert "user-read-currently-playing" in called_scopes
    assert called_state == "random_state"


def test_connect_spotify_account_success() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    spotify_auth = MagicMock(spec=SpotifyAuthPort)
    spotify_profile = MagicMock(spec=SpotifyUserProfilePort)

    user = User(
        user_id=10,
        email="user10@example.com",
        password_hash="pw",
        display_name="User Ten",
        plan_id=1,
    )
    user_repo.find_by_id.return_value = user
    user_repo.find_by_spotify_id.return_value = None
    user_repo.save.side_effect = lambda u: u

    spotify_auth.exchange_code.return_value = SpotifyTokens(
        access_token="tok_123",
        refresh_token="ref_456",
        expires_in=3600,
    )
    spotify_profile.get_current_user_profile.return_value = SpotifyUserProfile(
        id="spotify_id_999",
        display_name="Spotify User 999",
        product="premium",
    )

    use_case = ConnectSpotifyAccountUseCase(
        user_repo=user_repo,
        spotify_auth=spotify_auth,
        spotify_profile=spotify_profile,
    )

    updated = use_case.execute(user_id=10, code="auth_code_xyz")
    assert updated.spotify_id == "spotify_id_999"
    assert updated.spotify_premium is True
    assert updated.spotify_access_token == "tok_123"
    assert updated.spotify_refresh_token == "ref_456"
    assert updated.spotify_token_expires_at is not None
    user_repo.save.assert_called_once_with(user)


def test_connect_spotify_account_downgrades_when_profile_is_not_premium() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    spotify_auth = MagicMock(spec=SpotifyAuthPort)
    spotify_profile = MagicMock(spec=SpotifyUserProfilePort)

    user = User(
        user_id=10,
        email="user10@example.com",
        password_hash="pw",
        display_name="User Ten",
        plan_id=1,
        spotify_id="spotify_id_999",
        spotify_premium=True,
    )
    user_repo.find_by_id.return_value = user
    user_repo.find_by_spotify_id.return_value = user
    user_repo.save.side_effect = lambda u: u

    spotify_auth.exchange_code.return_value = SpotifyTokens(
        access_token="tok_123", expires_in=3600
    )
    spotify_profile.get_current_user_profile.return_value = SpotifyUserProfile(
        id="spotify_id_999",
        display_name="Spotify User 999",
        product="free",
    )

    use_case = ConnectSpotifyAccountUseCase(
        user_repo=user_repo,
        spotify_auth=spotify_auth,
        spotify_profile=spotify_profile,
    )

    updated = use_case.execute(user_id=10, code="auth_code_xyz")
    assert updated.spotify_premium is False
    user_repo.save.assert_called_once_with(user)


def test_connect_spotify_account_duplicate_raises_business_rule_violation() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    spotify_auth = MagicMock(spec=SpotifyAuthPort)
    spotify_profile = MagicMock(spec=SpotifyUserProfilePort)

    user = User(
        user_id=10,
        email="user10@example.com",
        password_hash="pw",
        display_name="User Ten",
        plan_id=1,
    )
    other_user = User(
        user_id=20,
        email="user20@example.com",
        password_hash="pw",
        display_name="Other User",
        plan_id=1,
        spotify_id="spotify_id_999",
    )
    user_repo.find_by_id.return_value = user
    user_repo.find_by_spotify_id.return_value = other_user

    spotify_auth.exchange_code.return_value = SpotifyTokens(
        access_token="tok_123", expires_in=3600
    )
    spotify_profile.get_current_user_profile.return_value = SpotifyUserProfile(
        id="spotify_id_999",
        display_name="Spotify User 999",
    )

    use_case = ConnectSpotifyAccountUseCase(
        user_repo=user_repo,
        spotify_auth=spotify_auth,
        spotify_profile=spotify_profile,
    )

    with pytest.raises(BusinessRuleViolationError, match="already linked"):
        use_case.execute(user_id=10, code="auth_code_xyz")


def test_connect_spotify_account_user_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    spotify_auth = MagicMock(spec=SpotifyAuthPort)
    spotify_profile = MagicMock(spec=SpotifyUserProfilePort)
    user_repo.find_by_id.return_value = None

    use_case = ConnectSpotifyAccountUseCase(
        user_repo=user_repo,
        spotify_auth=spotify_auth,
        spotify_profile=spotify_profile,
    )

    with pytest.raises(EntityNotFoundError):
        use_case.execute(user_id=999, code="code")
