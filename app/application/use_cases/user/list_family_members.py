"""Use case for listing dependent family members."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class ListFamilyMembersUseCase:
    """Lists all dependent profiles linked to a primary family account."""

    user_repo: UserRepositoryPort

    def execute(self, primary_user_id: int) -> list[User]:
        primary_user = self.user_repo.find_by_id(primary_user_id)
        if not primary_user:
            raise EntityNotFoundError(f"Primary user {primary_user_id} not found.")

        return self.user_repo.list_dependents(primary_user_id)
