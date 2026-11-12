"""Use case for listing user interaction history."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import Interaction, InteractionAction


@dataclass(slots=True, frozen=True)
class ListUserInteractionsUseCase:
    """Retrieves interaction history for a user, optionally filtered by action."""

    user_repo: UserRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_repo: TrackRepositoryPort

    def execute(
        self, user_id: int, action: InteractionAction | None = None
    ) -> list[Interaction]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        interactions = self.interaction_repo.list_by_user(user_id, action=action)
        track_ids = [interaction.track_id for interaction in interactions]
        tracks_by_id = self.track_repo.find_by_ids(track_ids)
        visible: list[Interaction] = []
        for interaction in interactions:
            track = tracks_by_id.get(interaction.track_id)
            if (
                track is not None
                and not track.is_deleted
                and not user.is_track_restricted_for_minor(track)
            ):
                visible.append(interaction)
        return visible
