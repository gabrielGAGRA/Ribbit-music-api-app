"""Unit tests for CreateJamUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import CreateJamCommand
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.create_jam import CreateJamUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_create_jam_success_strips_room_name_and_saves_jam() -> None:
    host = User(
        user_id=7,
        email="host@ribbit.com",
        password_hash="pw",
        display_name="DJ Frog",
        age=24,
        plan_id=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.save.side_effect = lambda j: j

    use_case = CreateJamUseCase(jam_repo=jam_repo, user_repo=user_repo)
    command = CreateJamCommand(host_user_id=7, room_name="  Late Night Pond  ")

    result = use_case.execute(command)

    assert result.host_user_id == 7
    assert result.room_name == "Late Night Pond"
    assert result.is_active is True
    assert len(result.room_code) == 6 and result.room_code.isdigit()
    user_repo.find_by_id.assert_called_once_with(7)
    jam_repo.save.assert_called_once_with(result)


def test_create_jam_host_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    jam_repo = MagicMock(spec=JamRepositoryPort)

    use_case = CreateJamUseCase(jam_repo=jam_repo, user_repo=user_repo)
    command = CreateJamCommand(host_user_id=999, room_name="Room")

    with pytest.raises(EntityNotFoundError, match="Host user 999 not found"):
        use_case.execute(command)

    jam_repo.save.assert_not_called()


def test_create_jam_registers_host_as_participant() -> None:
    from app.domain.models import Jam

    host = User(
        user_id=7,
        email="host@ribbit.com",
        password_hash="pw",
        display_name="DJ Frog",
        age=24,
        plan_id=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host

    saved_jam = Jam(
        jam_id=42, host_user_id=7, room_name="Pond", room_code="123456", is_active=True
    )
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.save.return_value = saved_jam

    use_case = CreateJamUseCase(jam_repo=jam_repo, user_repo=user_repo)
    command = CreateJamCommand(host_user_id=7, room_name="Pond")

    result = use_case.execute(command)

    assert result == saved_jam
    jam_repo.add_participant.assert_called_once_with(42, 7)


def test_create_jam_invalid_deck_source_raises_business_rule_error() -> None:
    from app.domain.exceptions import BusinessRuleViolationError

    host = User(
        user_id=7,
        email="host@ribbit.com",
        password_hash="pw",
        display_name="DJ Frog",
        age=24,
        plan_id=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host
    jam_repo = MagicMock(spec=JamRepositoryPort)

    use_case = CreateJamUseCase(jam_repo=jam_repo, user_repo=user_repo)
    command = CreateJamCommand(
        host_user_id=7, room_name="Pond", deck_source="invalid_source"
    )

    with pytest.raises(BusinessRuleViolationError, match="Deck source must be"):
        use_case.execute(command)


def test_create_jam_playlist_source_validates_host_ownership() -> None:
    from app.application.ports.repositories.playlist_repository import (
        PlaylistRepositoryPort,
    )
    from app.domain.exceptions import PermissionDeniedError
    from app.domain.models import Playlist

    host = User(
        user_id=7,
        email="host@ribbit.com",
        password_hash="pw",
        display_name="DJ Frog",
        age=24,
        plan_id=2,
    )
    # Playlist belongs to user 99, not host 7
    other_playlist = Playlist(playlist_id=12, user_id=99, name="Other's list")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host

    jam_repo = MagicMock(spec=JamRepositoryPort)
    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = other_playlist

    use_case = CreateJamUseCase(
        jam_repo=jam_repo, user_repo=user_repo, playlist_repo=playlist_repo
    )
    command = CreateJamCommand(
        host_user_id=7,
        room_name="Pond",
        deck_source="playlist",
        source_playlist_id=12,
    )

    with pytest.raises(
        PermissionDeniedError, match="Source playlist does not exist or does not belong"
    ):
        use_case.execute(command)
