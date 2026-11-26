"""Use case for authenticating users via Google Identity Provider."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.dtos.auth_dtos import (
    AuthenticateWithGoogleCommand,
    AuthResult,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.google_auth import GoogleIdpVerifierPort
lazy from app.application.ports.services.token_service import TokenServicePort


@dataclass(slots=True, frozen=True)
class AuthenticateWithGoogleUseCase:
    """Verifies Google ID token and authenticates an existing Ribbit user."""

    user_repo: UserRepositoryPort
    token_service: TokenServicePort
    google_verifier: GoogleIdpVerifierPort
    plan_repo: PlanRepositoryPort | None = None

    def execute(self, command: AuthenticateWithGoogleCommand) -> AuthResult:
        info = self.google_verifier.verify_id_token(command.id_token)

        user = self.user_repo.find_by_email(info.email)
        if user is None:
            raise EntityNotFoundError(
                "Nenhuma conta Ribbit encontrada para este e-mail Google. Conclua seu cadastro.",
                entity_name="User",
                details={
                    "registration_required": True,
                    "email": info.email,
                    "display_name": info.name,
                },
            )

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


__all__ = ["AuthenticateWithGoogleUseCase"]
