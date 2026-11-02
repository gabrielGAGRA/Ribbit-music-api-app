"""Use case for retrieving recently interacted tracks for a user."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.dtos.review_dtos import UserTrackInteractionResult
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetRecentlyInteractedTracksUseCase:
    """Returns recent track swipe interactions paired with active track entities."""

    user_repo: UserRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_repo: TrackRepositoryPort

    def execute(
        self, user_id: int, limit: int = 20
    ) -> list[UserTrackInteractionResult]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        interactions = self.interaction_repo.list_by_user(user_id)
        results: list[UserTrackInteractionResult] = []
        for interaction in interactions:
            track = self.track_repo.find_by_id(interaction.track_id)
            if track and not track.is_deleted:
                results.append(
                    UserTrackInteractionResult(
                        interaction=interaction,
                        track=track,
                    )
                )
                if len(results) >= limit:
                    break

        return results


__all__ = ["GetRecentlyInteractedTracksUseCase"]
