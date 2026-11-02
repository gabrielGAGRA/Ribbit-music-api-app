"""Unit tests for AddFamilyMemberUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.add_family_member import AddFamilyMemberUseCase
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_add_family_member_primary_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Primary user 1 not found"):
        use_case.execute(primary_user_id=1, dependent_user_id=2)

    user_repo.save.assert_not_called()


def test_add_family_member_plan_not_found_raises_error() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=99,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Plan with ID 99 not found"):
        use_case.execute(primary_user_id=1, dependent_user_id=2)

    user_repo.save.assert_not_called()


def test_add_family_member_plan_disallows_dependents_raises_permission_denied() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=2,
    )
    individual_plan = Plan(
        plan_id=2,
        name="Premium Individual",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = individual_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError,
        match="Current plan does not support adding family members",
    ):
        use_case.execute(primary_user_id=1, dependent_user_id=2)

    user_repo.save.assert_not_called()


def test_add_family_member_by_dependent_user_raises_permission_denied() -> None:
    dependent_caller = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=20,
        plan_id=3,
        primary_account_id=1,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = dependent_caller
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError,
        match="A dependent user cannot manage family members",
    ):
        use_case.execute(primary_user_id=2, dependent_user_id=3)

    user_repo.save.assert_not_called()


def test_add_family_member_self_link_raises_business_rule_violation() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        BusinessRuleViolationError,
        match="A user cannot add themselves as a dependent",
    ):
        use_case.execute(primary_user_id=1, dependent_user_id=1)

    user_repo.save.assert_not_called()


def test_add_family_member_dependent_user_not_found_raises_error() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, None]
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Dependent user 2 not found"):
        use_case.execute(primary_user_id=1, dependent_user_id=2)

    user_repo.save.assert_not_called()


def test_add_family_member_already_linked_to_same_primary_is_idempotent() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    dependent_user = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=19,
        plan_id=3,
        primary_account_id=1,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, dependent_user]
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute(primary_user_id=1, dependent_user_id=2)

    assert result is dependent_user
    user_repo.list_dependents.assert_not_called()
    user_repo.save.assert_not_called()


def test_add_family_member_linked_to_another_family_raises_business_rule_violation() -> (
    None
):
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    dependent_user = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=19,
        plan_id=3,
        primary_account_id=99,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, dependent_user]
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        BusinessRuleViolationError,
        match="already linked to another family account",
    ):
        use_case.execute(primary_user_id=1, dependent_user_id=2)

    user_repo.save.assert_not_called()


def test_add_family_member_quota_exceeded_raises_business_rule_violation() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    existing_dependent = User(
        user_id=2,
        email="dep1@test.com",
        password_hash="hash",
        display_name="Dep1",
        age=18,
        plan_id=3,
        primary_account_id=1,
    )
    new_dependent = User(
        user_id=3,
        email="dep2@test.com",
        password_hash="hash",
        display_name="Dep2",
        age=16,
        plan_id=1,
    )
    duo_plan = Plan(
        plan_id=3,
        name="Duo",
        initial_monthly_price=24.90,
        initial_max_profiles=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, new_dependent]
    user_repo.list_dependents.return_value = [existing_dependent]
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = duo_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        BusinessRuleViolationError,
        match="Family plan profile limit of 2 reached",
    ):
        use_case.execute(primary_user_id=1, dependent_user_id=3)

    user_repo.save.assert_not_called()


def test_add_family_member_links_account_and_updates_plan_successfully() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    dependent_user = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=15,
        plan_id=1,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, dependent_user]
    user_repo.list_dependents.return_value = []
    user_repo.save.side_effect = lambda u: u
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute(primary_user_id=1, dependent_user_id=2)

    assert result is dependent_user
    assert result.primary_account_id == 1
    assert result.plan_id == 3
    user_repo.save.assert_called_once_with(dependent_user)


def test_add_family_member_provisioning_minor_succeeds() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    user_repo.find_by_email.return_value = None
    user_repo.list_dependents.return_value = []
    user_repo.save.side_effect = lambda u: u

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute(
        primary_user_id=1,
        email="child@test.com",
        password="secretpassword",
        display_name="Child Profile",
        birth_date="2014-06-10",
    )

    assert result.email == "child@test.com"
    assert result.display_name == "Child Profile"
    assert result.primary_account_id == 1
    assert result.plan_id == 3
    assert result.birth_date == "2014-06-10"
    assert result.is_minor() is True
    user_repo.save.assert_called_once()


def test_add_family_member_provisioning_duplicate_email_raises_duplicate_entity() -> (
    None
):
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    existing_user = User(
        user_id=5,
        email="taken@test.com",
        password_hash="hash",
        display_name="Taken",
        age=22,
        plan_id=1,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    user_repo.find_by_email.return_value = existing_user
    user_repo.list_dependents.return_value = []

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(DuplicateEntityError, match="já está em uso"):
        use_case.execute(
            primary_user_id=1,
            email="taken@test.com",
            password="secretpassword",
            display_name="Taken",
            birth_date="2012-01-01",
        )


def test_add_family_member_provisioning_future_birth_date_raises_violation() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=30,
        plan_id=3,
    )
    family_plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=6,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    user_repo.find_by_email.return_value = None
    user_repo.list_dependents.return_value = []

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = AddFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(BusinessRuleViolationError, match="não pode estar no futuro"):
        use_case.execute(
            primary_user_id=1,
            email="future@test.com",
            password="secretpassword",
            display_name="Future",
            birth_date="2099-01-01",
        )
