"""Use case for authenticating users."""

from dataclasses import dataclass

from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
lazy from app.application.dtos.auth_dtos import (
    AuthenticateUserCommand,
    AuthResult,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.application.ports.services.token_service import TokenServicePort


@dataclass(slots=True, frozen=True)
class AuthenticateUserUseCase:
    """Verifies user email and password credentials."""

    user_repo: UserRepositoryPort
    password_hasher: PasswordHasherPort
    token_service: TokenServicePort
    plan_repo: PlanRepositoryPort | None = None

    def execute(self, command: AuthenticateUserCommand) -> AuthResult:
        user = self.user_repo.find_by_email(command.email.strip().lower())
        if not user:
            raise AuthenticationRequiredError("Invalid credentials.")

        if not self.password_hasher.verify_password(
            command.password, user.password_hash
        ):
            raise AuthenticationRequiredError("Invalid credentials.")

        if not user.is_admin and user.is_minor() and self.plan_repo is not None:
            plan = self.plan_repo.find_by_id(user.plan_id)
            if not user.can_use_plan(plan):
                raise PermissionDeniedError(
                    "Minor users cannot use the Free plan and must be linked to an active Family plan."
                )

        if user.user_id is None:
            raise RuntimeError("Authenticated user is missing its persisted ID.")
        token = self.token_service.create_access_token(
            user_id=user.user_id, is_admin=user.is_admin
        )

        return AuthResult(user=user, access_token=token)
