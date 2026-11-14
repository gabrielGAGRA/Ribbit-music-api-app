"""Unit tests for Spotify Premium guard and automatic 1 -> 0 downgrade."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.spotify.premium_guard import (
    execute_with_spotify_premium,
    require_spotify_premium,
)
from app.domain.exceptions import (
    SpotifyAuthError,
    SpotifyConnectionRequiredError,
    SpotifyForbiddenError,
    SpotifyPremiumRequiredError,
)
from app.domain.models.user import User
from app.presentation.exception_handlers import resolve_status_code


def _user(*, spotify_id: str | None = "spot_7", spotify_premium: bool) -> User:
    return User(
        user_id=7,
        email="listener@example.com",
        password_hash="pw",
        display_name="Listener",
        age=25,
        plan_id=1,
        spotify_id=spotify_id,
        spotify_premium=spotify_premium,
    )


def test_require_spotify_premium_allows_premium_and_blocks_free() -> None:
    require_spotify_premium(_user(spotify_premium=True))

    with pytest.raises(SpotifyPremiumRequiredError) as exc_info:
        require_spotify_premium(_user(spotify_premium=False))
    assert resolve_status_code(exc_info.value) == 403


def test_require_spotify_premium_raises_connection_required_when_unlinked() -> None:
    with pytest.raises(SpotifyConnectionRequiredError) as exc_info:
        require_spotify_premium(_user(spotify_id=None, spotify_premium=False))
    assert resolve_status_code(exc_info.value) == 403
    assert exc_info.value.details.get("rule_name") == "spotify_connection_required"


def test_execute_with_spotify_premium_downgrades_on_premium_required_error() -> None:
    user = _user(spotify_premium=True)
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.save.side_effect = lambda u: u

    def _failing_op() -> None:
        raise SpotifyPremiumRequiredError("Player command failed: Premium required")

    with pytest.raises(SpotifyPremiumRequiredError):
        execute_with_spotify_premium(user_repo, user, _failing_op)

    assert user.spotify_premium is False
    user_repo.save.assert_called_once_with(user)


def test_execute_with_spotify_premium_does_not_downgrade_on_other_errors() -> None:
    user = _user(spotify_premium=True)
    user_repo = MagicMock(spec=UserRepositoryPort)

    def _scope_error() -> None:
        raise SpotifyForbiddenError("Missing scope")

    with pytest.raises(SpotifyForbiddenError):
        execute_with_spotify_premium(user_repo, user, _scope_error)

    def _auth_error() -> None:
        raise SpotifyAuthError("Expired token")

    with pytest.raises(SpotifyAuthError):
        execute_with_spotify_premium(user_repo, user, _auth_error)

    assert user.spotify_premium is True
    user_repo.save.assert_not_called()
