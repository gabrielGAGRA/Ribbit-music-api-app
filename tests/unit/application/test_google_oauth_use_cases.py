"""Unit tests for Google OAuth use cases."""

from unittest.mock import MagicMock

from app.application.dtos.auth_dtos import AuthenticateWithGoogleCommand, AuthResult
from app.application.ports.services.google_auth import GoogleOAuthPort
from app.application.use_cases.auth.authenticate_with_google import (
    AuthenticateWithGoogleUseCase,
)
from app.application.use_cases.auth.complete_google_oauth import (
    CompleteGoogleOAuthUseCase,
)
from app.application.use_cases.auth.get_google_authorize_url import (
    GetGoogleAuthorizeUrlUseCase,
)
from app.domain.models.user import User


def test_get_google_authorize_url_use_case() -> None:
    oauth_port = MagicMock(spec=GoogleOAuthPort)
    oauth_port.build_authorize_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?state=s123"
    )

    use_case = GetGoogleAuthorizeUrlUseCase(oauth_port=oauth_port)
    url = use_case.execute(state="s123", code_challenge="c456")

    assert url == "https://accounts.google.com/o/oauth2/auth?state=s123"
    oauth_port.build_authorize_url.assert_called_once_with(
        state="s123", code_challenge="c456"
    )


def test_complete_google_oauth_use_case() -> None:
    oauth_port = MagicMock(spec=GoogleOAuthPort)
    auth_with_google_uc = MagicMock(spec=AuthenticateWithGoogleUseCase)

    oauth_port.exchange_code.return_value = "id_token_xyz"
    dummy_user = User(
        user_id=1,
        email="test@example.com",
        password_hash="pw",
        display_name="Test",
        plan_id=1,
    )
    auth_with_google_uc.execute.return_value = AuthResult(
        user=dummy_user, access_token="jwt_ribbit_123"
    )

    use_case = CompleteGoogleOAuthUseCase(
        oauth_port=oauth_port,
        authenticate_with_google_use_case=auth_with_google_uc,
    )

    result = use_case.execute(code="code_123", code_verifier="verifier_abc")

    assert result.access_token == "jwt_ribbit_123"
    assert result.user.email == "test@example.com"
    oauth_port.exchange_code.assert_called_once_with(
        code="code_123", code_verifier="verifier_abc"
    )
    auth_with_google_uc.execute.assert_called_once_with(
        AuthenticateWithGoogleCommand(id_token="id_token_xyz")
    )
