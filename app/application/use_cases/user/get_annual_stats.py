"""Use case for calculating annual listening metrics for Premium subscribers."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.dtos.user_dtos import AnnualStatsResult
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.repositories.user_stats_repository import (
    UserStatsRepositoryPort,
)


@dataclass(slots=True, frozen=True)
class GetAnnualListeningStatsUseCase:
    """Generates aggregated user statistics exclusive to Premium subscribers."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    user_stats_repo: UserStatsRepositoryPort

    def execute(self, user_id: int, year: int | None = None) -> AnnualStatsResult:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan or not plan.is_paid:
            raise PermissionDeniedError("Feature exclusive to Premium subscribers.")

        return self.user_stats_repo.get_user_stats(user_id=user_id, year=year)
