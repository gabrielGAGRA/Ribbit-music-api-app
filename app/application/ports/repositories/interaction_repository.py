"""Persistence port for swipe interactions."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models import Interaction, InteractionAction


@runtime_checkable
class InteractionRepositoryPort(Protocol):
    def find_by_user_and_track(
        self, user_id: int, track_id: int
    ) -> Interaction | None: ...

    def save(self, interaction: Interaction) -> Interaction: ...

    def list_by_user(
        self, user_id: int, action: InteractionAction | None = None
    ) -> list[Interaction]: ...

    def list_interacted_track_ids(self, user_id: int) -> list[int]: ...
