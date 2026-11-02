"""Use case for authenticating users."""

from dataclasses import dataclass

from app.domain.exceptions import AuthenticationRequiredError
lazy from app.application.dtos.auth_dtos import (
    AuthenticateUserCommand,
    AuthResult,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.application.ports.services.token_service import TokenServicePort


@dataclass(slots=True, frozen=True)
class AuthenticateUserUseCase:
    """Verifies user email and password credentials."""

    user_repo: UserRepositoryPort
    password_hasher: PasswordHasherPort
    token_service: TokenServicePort | None = None

    def execute(self, command: AuthenticateUserCommand) -> AuthResult:
        user = self.user_repo.find_by_email(command.email.strip().lower())
        if not user:
            raise AuthenticationRequiredError("Invalid credentials.")

        if not self.password_hasher.verify_password(
            command.password, user.password_hash
        ):
            raise AuthenticationRequiredError("Invalid credentials.")

        token = ""
        if self.token_service is not None and user.user_id is not None:
            token = self.token_service.create_access_token(
                user_id=user.user_id, is_admin=user.is_admin
            )

        return AuthResult(user=user, access_token=token)
