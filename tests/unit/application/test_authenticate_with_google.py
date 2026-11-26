"""Unit tests for AuthenticateWithGoogleUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import AuthenticateWithGoogleCommand
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.google_auth import (
    GoogleIdpVerifierPort,
    GoogleUserInfo,
)
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth.authenticate_with_google import (
    AuthenticateWithGoogleUseCase,
)
from app.domain.exceptions import (
    AuthenticationRequiredError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.plan import Plan
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


def test_authenticate_with_google_rejects_minor_on_free_plan() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)
    google_verifier = MagicMock(spec=GoogleIdpVerifierPort)

    minor_user = User(
        user_id=43,
        email="minor@example.com",
        password_hash="hashed_pw",
        display_name="Minor User",
        age=16,
        plan_id=1,
    )
    user_repo.find_by_email.return_value = minor_user
    plan_repo.find_by_id.return_value = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    google_verifier.verify_id_token.return_value = GoogleUserInfo(
        email="minor@example.com",
        email_verified=True,
        name="Minor User",
        sub="sub-minor-43",
    )

    use_case = AuthenticateWithGoogleUseCase(
        user_repo=user_repo,
        token_service=token_service,
        google_verifier=google_verifier,
        plan_repo=plan_repo,
    )

    with pytest.raises(
        PermissionDeniedError, match="Minor users cannot use the Free plan"
    ):
        use_case.execute(AuthenticateWithGoogleCommand(id_token="google_token_minor"))
    token_service.create_access_token.assert_not_called()
