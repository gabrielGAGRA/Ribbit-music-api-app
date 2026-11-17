"""Unit tests for AuthenticateWithGoogleUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import AuthenticateWithGoogleCommand
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.google_auth import (
    GoogleIdpVerifierPort,
    GoogleUserInfo,
)
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth.authenticate_with_google import (
    AuthenticateWithGoogleUseCase,
)
from app.domain.exceptions import AuthenticationRequiredError, EntityNotFoundError
from app.domain.models.user import User


def test_authenticate_with_google_existing_user() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)
    google_verifier = MagicMock(spec=GoogleIdpVerifierPort)

    existing_user = User(
        user_id=42,
        email="existing@example.com",
        password_hash="hashed_pw",
        display_name="Existing User",
        plan_id=1,
    )
    user_repo.find_by_email.return_value = existing_user
    google_verifier.verify_id_token.return_value = GoogleUserInfo(
        email="existing@example.com",
        email_verified=True,
        name="Google Name",
        sub="sub-123",
    )
    token_service.create_access_token.return_value = "jwt_token_existing"

    use_case = AuthenticateWithGoogleUseCase(
        user_repo=user_repo,
        token_service=token_service,
        google_verifier=google_verifier,
    )

    result = use_case.execute(
        AuthenticateWithGoogleCommand(id_token="google_token_abc")
    )

    assert result.user.user_id == 42
    assert result.access_token == "jwt_token_existing"
    user_repo.save.assert_not_called()


def test_authenticate_with_google_unregistered_user_raises_registration_required() -> (
    None
):
    user_repo = MagicMock(spec=UserRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)
    google_verifier = MagicMock(spec=GoogleIdpVerifierPort)

    user_repo.find_by_email.return_value = None
    google_verifier.verify_id_token.return_value = GoogleUserInfo(
        email="newbie@example.com",
        email_verified=True,
        name="Newbie User",
        sub="sub-newbie-999",
    )

    use_case = AuthenticateWithGoogleUseCase(
        user_repo=user_repo,
        token_service=token_service,
        google_verifier=google_verifier,
    )

    with pytest.raises(EntityNotFoundError) as exc_info:
        use_case.execute(AuthenticateWithGoogleCommand(id_token="google_token_new"))

    assert exc_info.value.details == {
        "entity_name": "User",
        "registration_required": True,
        "email": "newbie@example.com",
        "display_name": "Newbie User",
    }
    user_repo.save.assert_not_called()
    token_service.create_access_token.assert_not_called()


def test_authenticate_with_google_unverified_token_propagates_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)
    google_verifier = MagicMock(spec=GoogleIdpVerifierPort)

    google_verifier.verify_id_token.side_effect = AuthenticationRequiredError(
        "Invalid token"
    )

    use_case = AuthenticateWithGoogleUseCase(
        user_repo=user_repo,
        token_service=token_service,
        google_verifier=google_verifier,
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid token"):
        use_case.execute(AuthenticateWithGoogleCommand(id_token="bad_token"))
