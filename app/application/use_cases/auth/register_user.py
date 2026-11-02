"""Use case for registering a new platform user."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
lazy from app.application.dtos.auth_dtos import RegisterUserCommand
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class RegisterUserUseCase:
    """Coordinates registration of a new user account."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    password_hasher: PasswordHasherPort

    def execute(self, command: RegisterUserCommand) -> User:
        email = command.email.strip().lower()
        existing = self.user_repo.find_by_email(email)
        if existing:
            raise DuplicateEntityError(f"Email {email} is already in use.")

        age = command.age
        birth_date_str = command.birth_date.strip() if command.birth_date else None

        if birth_date_str:
            try:
                bdate = date.fromisoformat(birth_date_str)
            except (ValueError, TypeError) as exc:
                raise BusinessRuleViolationError(
                    "Data de nascimento inválida."
                ) from exc

            today = datetime.now(tz=UTC).date()
            if bdate > today:
                raise BusinessRuleViolationError(
                    "Data de nascimento não pode estar no futuro."
                )

            age = (
                today.year
                - bdate.year
                - ((today.month, today.day) < (bdate.month, bdate.day))
            )

        if age is None or age < 0:
            raise BusinessRuleViolationError("Data de nascimento inválida.")

        if User.is_age_minor(age):
            raise BusinessRuleViolationError(
                "Cadastro direto permitido apenas para maiores de 18 anos."
            )

        plan_id = command.plan_id
        if plan_id is None:
            free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
            if not free_plan or free_plan.plan_id is None:
                raise EntityNotFoundError("Default Free plan not found.")
            plan_id = free_plan.plan_id
        else:
            plan = self.plan_repo.find_by_id(plan_id)
            if not plan:
                raise EntityNotFoundError(f"Plan with ID {plan_id} not found.")

        hashed_password = self.password_hasher.hash_password(command.password)
        new_user = User(
            user_id=None,
            email=email,
            password_hash=hashed_password,
            display_name=command.display_name.strip(),
            age=age,
            plan_id=plan_id,
            is_admin=False,
            birth_date=birth_date_str,
        )
        return self.user_repo.save(new_user)
