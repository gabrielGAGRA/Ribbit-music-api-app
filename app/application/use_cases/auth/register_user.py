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

    @staticmethod
    def _resolve_age(command: RegisterUserCommand) -> tuple[int, str | None]:
        age = command.age
        birth_date_str = command.birth_date.strip() if command.birth_date else None

        if birth_date_str:
            try:
                bdate = date.fromisoformat(birth_date_str)
            except (ValueError, TypeError) as exc:
                raise BusinessRuleViolationError("Invalid birth date.") from exc

            today = datetime.now(tz=UTC).date()
            if bdate > today:
                raise BusinessRuleViolationError("Birth date cannot be in the future.")

            age = (
                today.year
                - bdate.year
                - ((today.month, today.day) < (bdate.month, bdate.day))
            )

        if age is None or age < 0:
            raise BusinessRuleViolationError("Invalid birth date.")
        return age, birth_date_str

    def _resolve_plan(self, plan_id: int | None) -> Plan:
        if plan_id is None:
            free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
            if not free_plan or free_plan.plan_id is None:
                raise EntityNotFoundError("Default Free plan not found.")
            return free_plan
        plan = self.plan_repo.find_by_id(plan_id)
        if not plan:
            raise EntityNotFoundError(f"Plan with ID {plan_id} not found.")
        return plan

    @staticmethod
    def _resolve_guardian(
        command: RegisterUserCommand,
        *,
        is_minor: bool,
        plan: Plan,
    ) -> tuple[str | None, str | None]:
        if is_minor:
            if (
                not command.guardian_confirmed_adult
                or not command.guardian_name
                or not command.guardian_email
            ):
                raise BusinessRuleViolationError(
                    "Direct registration only permitted for users 18 years or older."
                )
            if plan.allows_dependents is True:
                raise BusinessRuleViolationError(
                    "Minor users cannot subscribe as primary holder of a Family plan."
                )
            return command.guardian_name.strip(), command.guardian_email.strip().lower()

        if command.guardian_name or command.guardian_email:
            if not command.guardian_name or not command.guardian_email:
                raise BusinessRuleViolationError(
                    "Both guardian name and guardian email must be provided."
                )
            return command.guardian_name.strip(), command.guardian_email.strip().lower()
        return None, None

    def execute(self, command: RegisterUserCommand) -> User:
        email = command.email.strip().lower()
        if self.user_repo.find_by_email(email):
            raise DuplicateEntityError(f"Email {email} is already in use.")

        age, birth_date_str = self._resolve_age(command)
        is_minor = User.is_age_minor(age)
        if is_minor and (
            not command.guardian_confirmed_adult
            or not command.guardian_name
            or not command.guardian_email
        ):
            raise BusinessRuleViolationError(
                "Direct registration only permitted for users 18 years or older."
            )

        plan = self._resolve_plan(command.plan_id)
        if plan.plan_id is None:
            raise EntityNotFoundError("Resolved plan is missing its persisted ID.")
        guardian_name, guardian_email = self._resolve_guardian(
            command, is_minor=is_minor, plan=plan
        )

        hashed_password = self.password_hasher.hash_password(command.password)
        new_user = User(
            user_id=None,
            email=email,
            password_hash=hashed_password,
            display_name=command.display_name.strip(),
            age=age,
            plan_id=plan.plan_id,
            is_admin=False,
            birth_date=birth_date_str,
            blocked_genres=frozenset(command.blocked_genres),
            favorite_genres=frozenset(command.favorite_genres),
            preferred_theme=command.preferred_theme,
        )
        if guardian_name is not None and guardian_email is not None:
            try:
                new_user.assign_guardian(guardian_name, guardian_email)
            except ValueError as exc:
                raise BusinessRuleViolationError(str(exc)) from exc
        return self.user_repo.save(new_user)
