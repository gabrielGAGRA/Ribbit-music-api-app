"""Use case for promoting a user to administrator status."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class PromoteUserToAdminUseCase:
    """Grants administrator privileges to an existing user."""

    user_repo: UserRepositoryPort

    def execute(self, user_id: int) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User {user_id} not found.")

        user.promote_to_admin()
        return self.user_repo.save(user)
