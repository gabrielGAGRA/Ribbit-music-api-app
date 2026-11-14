"""Unit tests for Spotify connection presentation router."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.spotify import (
    ConnectSpotifyAccountUseCase,
    GetSpotifyAuthorizeUrlUseCase,
)
from app.domain.exceptions import AuthenticationRequiredError
from app.domain.models.user import User
from app.infrastructure.security.token_service import HMACTokenService
from app.presentation.routers.spotify import (
    connect_spotify_callback,
    get_spotify_authorize_url,
)
from app.presentation.schemas.spotify import SpotifyConnectCallbackRequest


def test_get_spotify_authorize_url_generates_signed_state() -> None:
    token_service = HMACTokenService(secret_key="secret-key")
    mock_use_case = MagicMock(spec=GetSpotifyAuthorizeUrlUseCase)
    mock_use_case.execute.side_effect = lambda state: (
        f"https://accounts.spotify.com/authorize?state={state}"
    )

    response = get_spotify_authorize_url(
        user_id=42,
        use_case=mock_use_case,
        token_service=token_service,
    )

    assert "https://accounts.spotify.com/authorize?state=" in response.authorization_url
    mock_use_case.execute.assert_called_once()
    state_arg = mock_use_case.execute.call_args.kwargs.get("state")
    claims = token_service.decode_access_token(state_arg)
    assert claims.get("sub") == "42"


def test_connect_spotify_callback_success() -> None:
    token_service = HMACTokenService(secret_key="secret-key")
    state = token_service.create_access_token(user_id=42)

    mock_use_case = MagicMock(spec=ConnectSpotifyAccountUseCase)
    mock_use_case.execute.return_value = User(
        user_id=42,
        email="test@ribbit.com",
        password_hash="pw",
        display_name="Tester",
        plan_id=1,
        spotify_id="spot_123",
    )

    req = SpotifyConnectCallbackRequest(code="valid_code", state=state)
    response = connect_spotify_callback(
        req=req,
        user_id=42,
        use_case=mock_use_case,
        token_service=token_service,
    )

    assert response.user_id == 42
    assert response.spotify_id == "spot_123"
    mock_use_case.execute.assert_called_once_with(user_id=42, code="valid_code")


def test_connect_spotify_callback_rejects_mismatched_state_user() -> None:
    token_service = HMACTokenService(secret_key="secret-key")
    state_for_other_user = token_service.create_access_token(user_id=999)

    mock_use_case = MagicMock(spec=ConnectSpotifyAccountUseCase)
    req = SpotifyConnectCallbackRequest(code="valid_code", state=state_for_other_user)

    with pytest.raises(AuthenticationRequiredError, match="Invalid or mismatched"):
        connect_spotify_callback(
            req=req,
            user_id=42,
            use_case=mock_use_case,
            token_service=token_service,
        )
    mock_use_case.execute.assert_not_called()


def test_connect_spotify_callback_rejects_invalid_state() -> None:
    token_service = MagicMock(spec=TokenServicePort)
    token_service.decode_access_token.side_effect = AuthenticationRequiredError(
        "Invalid token"
    )

    mock_use_case = MagicMock(spec=ConnectSpotifyAccountUseCase)
    req = SpotifyConnectCallbackRequest(code="code", state="bogus_state")

    with pytest.raises(AuthenticationRequiredError):
        connect_spotify_callback(
            req=req,
            user_id=42,
            use_case=mock_use_case,
            token_service=token_service,
        )
