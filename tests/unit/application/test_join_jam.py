"""Unit tests for JoinJamUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.join_jam import JoinJamUseCase
from app.domain.exceptions import (
    EntityNotFoundError,
    SpotifyConnectionRequiredError,
    SpotifyPremiumRequiredError,
)
from app.domain.models import User
from app.domain.models.jam import Jam


def test_join_jam_success_normalizes_room_code_and_returns_jam() -> None:
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Pond Party",
        room_code="JAM-ABC123",
        is_active=True,
    )
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_code.return_value = jam

    use_case = JoinJamUseCase(jam_repo=jam_repo)
    result = use_case.execute("  jam-abc123  ")

    assert result is jam
    jam_repo.find_by_code.assert_called_once_with("JAM-ABC123")


def test_join_jam_not_found_raises_entity_not_found() -> None:
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_code.return_value = None

    use_case = JoinJamUseCase(jam_repo=jam_repo)

    with pytest.raises(EntityNotFoundError, match="Jam room not found or inactive"):
        use_case.execute("JAM-MISSING")


def test_join_jam_inactive_room_raises_entity_not_found() -> None:
    inactive_jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Closed Party",
        room_code="JAM-CLOSED",
        is_active=False,
    )
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_code.return_value = inactive_jam

    use_case = JoinJamUseCase(jam_repo=jam_repo)

    with pytest.raises(EntityNotFoundError, match="Jam room not found or inactive"):
        use_case.execute("JAM-CLOSED")


def test_join_jam_blocks_unlinked_and_non_spotify_premium_user() -> None:
    unlinked_user = User(
        user_id=5,
        email="free@ribbit.com",
        password_hash="pw",
        display_name="Free User",
        age=22,
        plan_id=1,
        spotify_id=None,
        spotify_premium=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = unlinked_user
    jam_repo = MagicMock(spec=JamRepositoryPort)

    use_case = JoinJamUseCase(jam_repo=jam_repo, user_repo=user_repo)

    with pytest.raises(SpotifyConnectionRequiredError):
        use_case.execute(room_code="JAM-ABC123", user_id=5)

    linked_free_user = User(
        user_id=5,
        email="free@ribbit.com",
        password_hash="pw",
        display_name="Free User",
        age=22,
        plan_id=1,
        spotify_id="spot_5",
        spotify_premium=False,
    )
    user_repo.find_by_id.return_value = linked_free_user

    with pytest.raises(SpotifyPremiumRequiredError):
        use_case.execute(room_code="JAM-ABC123", user_id=5)
    jam_repo.add_participant.assert_not_called()
