"""Use case for listing user interaction history."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import Interaction, InteractionAction


@dataclass(slots=True, frozen=True)
class ListUserInteractionsUseCase:
    """Retrieves interaction history for a user, optionally filtered by action."""

    user_repo: UserRepositoryPort
    interaction_repo: InteractionRepositoryPort

    def execute(
        self, user_id: int, action: InteractionAction | None = None
    ) -> list[Interaction]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        return self.interaction_repo.list_by_user(user_id, action=action)
