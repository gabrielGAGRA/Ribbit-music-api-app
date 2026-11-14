"""Use case for exchanging Spotify authorization code and linking Spotify ID to user."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.spotify import (
    SpotifyAuthPort,
    SpotifyUserProfilePort,
)
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class ConnectSpotifyAccountUseCase:
    """Exchanges Spotify auth code, fetches profile, and associates Spotify ID."""

    user_repo: UserRepositoryPort
    spotify_auth: SpotifyAuthPort
    spotify_profile: SpotifyUserProfilePort

    def execute(self, user_id: int, code: str) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        tokens = self.spotify_auth.exchange_code(code.strip())
        profile = self.spotify_profile.get_current_user_profile(tokens.access_token)

        existing = self.user_repo.find_by_spotify_id(profile.id)
        if existing and existing.user_id != user.user_id:
            raise BusinessRuleViolationError(
                "This Spotify account is already linked to another Ribbit profile.",
                rule_name="unique_spotify_account",
            )

        user.link_spotify(profile.id)
        user.update_spotify_premium(profile.is_premium)
        expires_in = getattr(tokens, "expires_in", None)
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=max(0, int(expires_in)))
            if expires_in is not None
            else None
        )
        user.update_spotify_tokens(
            access_token=tokens.access_token,
            refresh_token=getattr(tokens, "refresh_token", None),
            expires_at=expires_at,
        )
        return self.user_repo.save(user)


__all__ = ["ConnectSpotifyAccountUseCase"]
