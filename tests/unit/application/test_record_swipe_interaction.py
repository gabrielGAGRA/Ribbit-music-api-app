"""Unit tests for RecordSwipeInteractionUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.discovery_dtos import RecordSwipeCommand
from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.discovery.record_swipe_interaction import (
    RecordSwipeInteractionUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.domain.models.interaction import InteractionAction
from app.domain.models.track import Track
from app.domain.models.user import User


@pytest.mark.parametrize(
    "action",
    [
        InteractionAction.LIKE,
        InteractionAction.SUPERLIKE,
        InteractionAction.DISLIKE,
    ],
)
def test_record_swipe_interaction_success_saves_interaction(
    action: InteractionAction,
) -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=20,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Ribbit Beats",
        artist="Swamp Crew",
        duration_seconds=195,
        genre="Hip-Hop",
        is_deleted=False,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.save.side_effect = lambda i: i

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(user_id=1, track_id=10, action=action)

    result = use_case.execute(command)

    assert result.user_id == 1
    assert result.track_id == 10
    assert result.action == action
    interaction_repo.save.assert_called_once_with(result)


def test_record_swipe_interaction_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    track_repo = MagicMock(spec=TrackRepositoryPort)
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=999,
        track_id=10,
        action=InteractionAction.LIKE,
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(command)

    interaction_repo.save.assert_not_called()


def test_record_swipe_interaction_track_not_found_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=20,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=1,
        track_id=404,
        action=InteractionAction.LIKE,
    )

    with pytest.raises(EntityNotFoundError, match="Track with ID 404 not found"):
        use_case.execute(command)

    interaction_repo.save.assert_not_called()


def test_record_swipe_interaction_soft_deleted_track_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=20,
        plan_id=1,
    )
    deleted_track = Track(
        track_id=10,
        title="Deleted Song",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        is_deleted=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = deleted_track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=1,
        track_id=10,
        action=InteractionAction.SUPERLIKE,
    )

    with pytest.raises(
        EntityNotFoundError, match="Track with ID 10 not found or inactive"
    ):
        use_case.execute(command)

    interaction_repo.save.assert_not_called()


def test_record_swipe_interaction_minor_on_explicit_track_raises_violation() -> None:
    minor_user = User(
        user_id=1,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Tadpole",
        age=14,
        plan_id=1,
    )
    explicit_track = Track(
        track_id=10,
        title="Explicit Song",
        artist="Artist",
        duration_seconds=180,
        genre="Rap",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor_user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = explicit_track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=1,
        track_id=10,
        action=InteractionAction.LIKE,
    )

    with pytest.raises(
        BusinessRuleViolationError, match="bloqueada para usuários menores"
    ):
        use_case.execute(command)

    interaction_repo.save.assert_not_called()


def test_record_swipe_interaction_blocked_genre_raises_violation() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
        blocked_genres=frozenset({"metal"}),
    )
    metal_track = Track(
        track_id=10,
        title="Heavy Beats",
        artist="Artist",
        duration_seconds=180,
        genre="Metal",
        explicit=False,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = metal_track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=1,
        track_id=10,
        action=InteractionAction.LIKE,
    )

    with pytest.raises(
        BusinessRuleViolationError, match="Gênero bloqueado pelo usuário"
    ):
        use_case.execute(command)

    interaction_repo.save.assert_not_called()


def test_record_swipe_interaction_string_synonym_action_saves_correctly() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Nice Track",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        explicit=False,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.save.side_effect = lambda i: i

    use_case = RecordSwipeInteractionUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    command = RecordSwipeCommand(
        user_id=1,
        track_id=10,
        action="amada",
    )

    result = use_case.execute(command)

    assert result.action == InteractionAction.SUPERLIKE
