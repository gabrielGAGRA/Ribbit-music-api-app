"""Use case for listing users and their assigned subscription plans."""

from dataclasses import dataclass

from app.application.dtos.admin_dtos import UserPlanSummaryResult
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class ListUsersWithPlansUseCase:
    """Lists users alongside their active plan names for administrative management."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    def execute(self) -> list[UserPlanSummaryResult]:
        users = self.user_repo.list_all()
        plans = {
            p.plan_id: p.name
            for p in self.plan_repo.list_all()
            if p.plan_id is not None
        }

        return [
            UserPlanSummaryResult(
                user_id=u.user_id,
                email=u.email,
                display_name=u.display_name,
                age=u.age,
                plan_name=plans.get(u.plan_id, "Unknown"),
                is_admin=u.is_admin,
            )
            for u in users
        ]
