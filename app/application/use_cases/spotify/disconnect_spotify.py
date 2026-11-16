"""Use case for unlinking a user's Spotify account."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class DisconnectSpotifyAccountUseCase:
    """Clears Spotify linkage, premium status, and OAuth tokens for a user."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int) -> User:
        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.unlink_spotify()
        return self.user_repo.save(user)


__all__ = ["DisconnectSpotifyAccountUseCase"]
