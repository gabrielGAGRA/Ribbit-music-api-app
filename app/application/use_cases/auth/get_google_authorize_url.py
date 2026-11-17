"""Use case for generating Google OAuth 2.0 authorization URL."""

from dataclasses import dataclass

lazy from app.application.ports.services.google_auth import GoogleOAuthPort


@dataclass(slots=True, frozen=True)
class GetGoogleAuthorizeUrlUseCase:
    """Generates the Google OAuth 2.0 authorization URL with requested state and PKCE."""

    oauth_port: GoogleOAuthPort

    def execute(self, state: str, code_challenge: str | None = None) -> str:
        return self.oauth_port.build_authorize_url(
            state=state, code_challenge=code_challenge
        )


__all__ = ["GetGoogleAuthorizeUrlUseCase"]
