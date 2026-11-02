"""Use case for listing platform administrators."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class ListAdministratorsUseCase:
    """Returns all users with administrator privileges."""

    user_repo: UserRepositoryPort

    def execute(self) -> list[User]:
        return [u for u in self.user_repo.list_all() if u.is_admin]


__all__ = ["ListAdministratorsUseCase"]
