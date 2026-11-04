"""Use case for authenticating users via Google Identity Provider."""

import secrets
from dataclasses import dataclass

lazy from app.application.dtos.auth_dtos import (
    AuthenticateWithGoogleCommand,
    AuthResult,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.google_auth import GoogleIdpVerifierPort
lazy from app.application.ports.services.token_service import TokenServicePort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class AuthenticateWithGoogleUseCase:
    """Verifies Google ID token and resolves or auto-provisions a Ribbit user."""

    user_repo: UserRepositoryPort
    token_service: TokenServicePort
    google_verifier: GoogleIdpVerifierPort

    def execute(self, command: AuthenticateWithGoogleCommand) -> AuthResult:
        info = self.google_verifier.verify_id_token(command.id_token)

        user = self.user_repo.find_by_email(info.email)
        if user is None:
            new_user = User(
                email=info.email,
                password_hash=f"oauth_google:{secrets.token_hex(16)}",
                display_name=info.name,
                age=None,
                plan_id=1,
            )
            user = self.user_repo.save(new_user)

        if user.user_id is None:
            raise RuntimeError("Authenticated user is missing its persisted ID.")

        token = self.token_service.create_access_token(
            user_id=user.user_id, is_admin=user.is_admin
        )
        return AuthResult(user=user, access_token=token)


__all__ = ["AuthenticateWithGoogleUseCase"]
