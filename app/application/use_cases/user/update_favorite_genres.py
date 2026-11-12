"""Use case for updating favorite music genres for a user."""

from dataclasses import dataclass
lazy from collections.abc import Sequence

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class UpdateFavoriteGenresUseCase:
    """Updates favorite music genres for a user."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int, favorite_genres: Sequence[str]) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        user.update_favorite_genres(favorite_genres)
        return self.user_repo.save(user)
