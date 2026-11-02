"""Use case for removing a dependent member from a family plan."""

from dataclasses import dataclass, field

from app.domain.exceptions import EntityNotFoundError
from app.domain.models.plan import Plan
from app.domain.services import FamilyPlanService
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class RemoveFamilyMemberUseCase:
    """Unlinks a dependent account from a primary account and reverts to Free plan."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    family_plan_service: FamilyPlanService = field(default_factory=FamilyPlanService)

    def execute(self, primary_user_id: int, member_user_id: int) -> User:
        primary_user = self.user_repo.find_by_id(primary_user_id)
        if not primary_user:
            raise EntityNotFoundError(f"Primary user {primary_user_id} not found.")

        member_user = self.user_repo.find_by_id(member_user_id)
        if not member_user:
            raise EntityNotFoundError(f"Member user {member_user_id} not found.")

        free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
        if not free_plan or free_plan.plan_id is None:
            raise EntityNotFoundError("Default Free plan not found.")

        self.family_plan_service.unlink_dependent(
            primary_user_id=primary_user_id,
            member_user=member_user,
            fallback_plan_id=free_plan.plan_id,
        )

        return self.user_repo.save(member_user)
