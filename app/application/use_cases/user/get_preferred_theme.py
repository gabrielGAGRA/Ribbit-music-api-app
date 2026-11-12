"""Use case for retrieving a user's preferred theme."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetPreferredThemeUseCase:
    """Gets the preferred UI theme configured for a user."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int) -> str:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        return user.preferred_theme
