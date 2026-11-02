"""Unit tests for CloseJamUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import CloseJamCommand
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.use_cases.jam.close_jam import CloseJamUseCase
from app.domain.exceptions import PermissionDeniedError
from app.domain.models import Jam


def test_close_jam_host_only_success() -> None:
    jam = Jam(jam_id=10, host_user_id=1, room_name="Pond", is_active=True)

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.save.side_effect = lambda j: j

    use_case = CloseJamUseCase(jam_repo=jam_repo)
    result = use_case.execute(CloseJamCommand(jam_id=10, host_user_id=1))

    assert result.is_active is False
    jam_repo.save.assert_called_once_with(jam)


def test_close_jam_non_host_raises_permission_denied() -> None:
    jam = Jam(jam_id=10, host_user_id=1, room_name="Pond", is_active=True)

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    use_case = CloseJamUseCase(jam_repo=jam_repo)
    with pytest.raises(PermissionDeniedError, match="Only the host"):
        use_case.execute(CloseJamCommand(jam_id=10, host_user_id=99))
