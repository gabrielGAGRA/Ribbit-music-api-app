"""Use case for exchanging Google OAuth code and resolving Ribbit user authentication."""

from dataclasses import dataclass

lazy from app.application.dtos.auth_dtos import (
    AuthenticateWithGoogleCommand,
    AuthResult,
)
lazy from app.application.ports.services.google_auth import GoogleOAuthPort
lazy from app.application.use_cases.auth.authenticate_with_google import (
    AuthenticateWithGoogleUseCase,
)


@dataclass(slots=True, frozen=True)
class CompleteGoogleOAuthUseCase:
    """Exchanges authorization code for Google ID token and provisions user session."""

    oauth_port: GoogleOAuthPort
    authenticate_with_google_use_case: AuthenticateWithGoogleUseCase

    def execute(self, code: str, code_verifier: str | None = None) -> AuthResult:
        id_token = self.oauth_port.exchange_code(code=code, code_verifier=code_verifier)
        return self.authenticate_with_google_use_case.execute(
            AuthenticateWithGoogleCommand(id_token=id_token)
        )


__all__ = ["CompleteGoogleOAuthUseCase"]
