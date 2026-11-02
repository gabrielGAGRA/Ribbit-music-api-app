"""Use case for recording user swipe interactions."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.domain.models.interaction import Interaction, InteractionAction
lazy from app.application.dtos.discovery_dtos import RecordSwipeCommand
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort

_ACTION_SYNONYMS: dict[str, InteractionAction] = {
    "like": InteractionAction.LIKE,
    "curtida": InteractionAction.LIKE,
    "superlike": InteractionAction.SUPERLIKE,
    "amada": InteractionAction.SUPERLIKE,
    "dislike": InteractionAction.DISLIKE,
    "deslike": InteractionAction.DISLIKE,
    "rejeitada": InteractionAction.DISLIKE,
    "rejeitar": InteractionAction.DISLIKE,
}


@dataclass(slots=True, frozen=True)
class RecordSwipeInteractionUseCase:
    """Records user gesture interactions (like, superlike, dislike) on tracks."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort

    def execute(self, command: RecordSwipeCommand) -> Interaction:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        track = self.track_repo.find_by_id(command.track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError(
                f"Track with ID {command.track_id} not found or inactive."
            )

        if user.is_minor() and track.explicit:
            raise BusinessRuleViolationError(
                "Música bloqueada para usuários menores de idade."
            )

        if track.genre.strip().lower() in user.blocked_genres:
            raise BusinessRuleViolationError("Gênero bloqueado pelo usuário.")

        if isinstance(command.action, InteractionAction):
            action_enum = command.action
        else:
            action_str = str(command.action).strip().lower()
            action_enum = _ACTION_SYNONYMS.get(action_str)
            if not action_enum:
                raise BusinessRuleViolationError(
                    f"Ação inválida '{command.action}'. Válidas: like, superlike, dislike."
                )

        interaction = Interaction(
            interaction_id=None,
            user_id=command.user_id,
            track_id=command.track_id,
            action=action_enum,
        )
        return self.interaction_repo.save(interaction)
