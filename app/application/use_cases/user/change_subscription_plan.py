"""Use case for changing user subscription plan."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class ChangeSubscriptionPlanUseCase:
    """Changes the subscription plan associated with a user and linked dependents."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    @staticmethod
    def _validate_minor_plan_change(
        user: User,
        new_plan: Plan,
        *,
        guardian_name: str | None,
        guardian_email: str | None,
        guardian_confirmed_adult: bool,
    ) -> None:
        if not user.is_minor():
            return
        if new_plan.allows_dependents is True:
            raise BusinessRuleViolationError(
                "Minor users cannot subscribe as primary holder of a Family plan."
            )
        if not new_plan.is_paid:
            return
        if guardian_name and guardian_email:
            if not guardian_confirmed_adult:
                raise BusinessRuleViolationError(
                    "Adult guardian confirmation is required for minor"
                    " Individual subscription."
                )
            try:
                user.assign_guardian(guardian_name, guardian_email)
            except ValueError as exc:
                raise BusinessRuleViolationError(str(exc)) from exc
            return
        if not (user.has_guardian() and guardian_confirmed_adult):
            raise BusinessRuleViolationError(
                "Adult guardian authorization is required for minor"
                " Individual subscription."
            )

    def execute(
        self,
        user_id: int,
        new_plan_id: int,
        *,
        guardian_name: str | None = None,
        guardian_email: str | None = None,
        guardian_confirmed_adult: bool = False,
    ) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if user.primary_account_id is not None:
            raise PermissionDeniedError(
                "Dependents cannot change the primary account subscription."
            )

        new_plan = self.plan_repo.find_by_id(new_plan_id)
        if not new_plan:
            raise EntityNotFoundError(f"Plan with ID {new_plan_id} not found.")

        self._validate_minor_plan_change(
            user,
            new_plan,
            guardian_name=guardian_name,
            guardian_email=guardian_email,
            guardian_confirmed_adult=guardian_confirmed_adult,
        )

        dependents = self.user_repo.list_dependents(user_id)
        if dependents and new_plan.max_profiles < len(dependents) + 1:
            raise BusinessRuleViolationError(
                "The new plan cannot accommodate currently linked members."
            )

        user.change_plan(new_plan_id)
        saved_user = self.user_repo.save(user)
        for dep in dependents:
            dep.change_plan(new_plan_id)
            self.user_repo.save(dep)

        return saved_user
