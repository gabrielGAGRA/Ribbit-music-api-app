"""Guards and automatic downgrade helpers for Spotify Premium-only features."""

lazy from collections.abc import Callable

from app.domain.exceptions import (
    SpotifyConnectionRequiredError,
    SpotifyPremiumRequiredError,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


def require_spotify_premium(user: User) -> None:
    """Raises SpotifyConnectionRequiredError or SpotifyPremiumRequiredError based on user state."""
    if user.spotify_premium:
        return
    if not user.spotify_id:
        raise SpotifyConnectionRequiredError(
            "Conecte sua conta do Spotify para utilizar o Pond.",
            details={"rule_name": "spotify_connection_required"},
        )
    raise SpotifyPremiumRequiredError(
        "Uma conta Spotify Premium é necessária para esta funcionalidade.",
        details={"rule_name": "spotify_premium_required"},
    )


def execute_with_spotify_premium[T](
    user_repo: UserRepositoryPort,
    user: User,
    operation: Callable[[], T],
) -> T:
    """Runs a Spotify Premium operation and downgrades spotify_premium on access denial."""
    require_spotify_premium(user)
    try:
        return operation()
    except SpotifyPremiumRequiredError:
        if user.spotify_premium:
            user.update_spotify_premium(False)
            user_repo.save(user)
        raise


__all__ = ["execute_with_spotify_premium", "require_spotify_premium"]
