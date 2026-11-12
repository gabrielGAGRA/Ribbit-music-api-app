"""Use case for updating a user's preferred theme."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class UpdatePreferredThemeUseCase:
    """Updates the preferred UI theme for a user."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int, preferred_theme: str) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        user.update_preferred_theme(preferred_theme)
        return self.user_repo.save(user)
