"""Use case for joining an existing Jam session via room code."""

import re
from dataclasses import dataclass

from app.application.dtos.jam_dtos import JoinJamCommand
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.jam import Jam

ROOM_CODE_PATTERN = re.compile(r"^(\d{6}|[A-Za-z0-9_\-]{3,20})$", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class JoinJamUseCase:
    """Finds an active Jam session by its room code and registers the participant."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort | None = None

    def execute(
        self,
        command_or_room_code: JoinJamCommand | str | None = None,
        room_code: str | None = None,
        user_id: int | None = None,
    ) -> Jam:
        if isinstance(command_or_room_code, JoinJamCommand):
            raw_code = command_or_room_code.room_code
            effective_user_id = command_or_room_code.user_id
        elif command_or_room_code is not None:
            raw_code = command_or_room_code
            effective_user_id = user_id
        elif room_code is not None:
            raw_code = room_code
            effective_user_id = user_id
        else:
            raise ValueError("room_code must be provided.")

        code = raw_code.strip().upper()
        if not ROOM_CODE_PATTERN.match(code):
            raise BusinessRuleViolationError("Room code format is invalid.")

        if effective_user_id and self.user_repo is not None:
            user = self.user_repo.find_by_id(effective_user_id)
            if not user:
                raise EntityNotFoundError(
                    f"User with ID {effective_user_id} not found."
                )

        jam = self.jam_repo.find_by_code(code)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if effective_user_id and jam.jam_id is not None:
            self.jam_repo.add_participant(jam.jam_id, effective_user_id)

        return jam
