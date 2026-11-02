"""Use case for associating a Spotify account ID with a user."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class LinkSpotifyAccountUseCase:
    """Links an external Spotify identifier to the user record."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int, spotify_id: str) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        user.link_spotify(spotify_id)
        return self.user_repo.save(user)
