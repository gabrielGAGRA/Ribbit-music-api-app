"""Domain service managing multi-entity family membership invariants."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    PermissionDeniedError,
)
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class FamilyPlanService:
    """Encapsulates cross-entity invariants for family plan membership and quotas."""

    def link_dependent(
        self,
        *,
        primary_user: User,
        dependent_user: User,
        plan: Plan,
        current_dependents_count: int,
    ) -> User:
        """Validates family plan rules and links dependent to primary user account."""
        if not plan.allows_dependents:
            raise PermissionDeniedError(
                "Current plan does not support adding family members."
            )

        if primary_user.primary_account_id is not None:
            raise PermissionDeniedError(
                "A dependent user cannot manage family members."
            )

        if (
            primary_user.user_id is not None
            and primary_user.user_id == dependent_user.user_id
        ):
            raise BusinessRuleViolationError(
                "A user cannot add themselves as a dependent."
            )

        if (
            primary_user.user_id is not None
            and dependent_user.primary_account_id == primary_user.user_id
        ):
            return dependent_user

        if dependent_user.primary_account_id is not None:
            raise BusinessRuleViolationError(
                "This user is already linked to another family account."
            )

        if not plan.can_accommodate_new_dependent(current_dependents_count):
            raise BusinessRuleViolationError(
                f"Family plan profile limit of {plan.max_profiles} reached."
            )

        if primary_user.user_id is not None:
            dependent_user.link_primary_account(primary_user.user_id)
        if plan.plan_id is not None:
            dependent_user.change_plan(plan.plan_id)
        return dependent_user

    def unlink_dependent(
        self,
        *,
        primary_user_id: int,
        member_user: User,
        fallback_plan_id: int,
    ) -> User:
        """Validates profile ownership and detaches dependent back to fallback plan."""
        if member_user.primary_account_id != primary_user_id:
            raise PermissionDeniedError(
                "This profile does not belong to your family account."
            )

        member_user.unlink_primary_account(fallback_plan_id)
        return member_user


__all__ = ["FamilyPlanService"]
