"""Use case for listing favorite music genres for a user."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class ListFavoriteGenresUseCase:
    """Lists all favorite genres configured on a user's profile."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int) -> list[str]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        return sorted(user.favorite_genres)
