"""Use case for adding a dependent member to a family plan."""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.services import FamilyPlanService
lazy from app.application.dtos.user_dtos import AddFamilyMemberCommand
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


def _default_hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"


@dataclass(slots=True, frozen=True)
class AddFamilyMemberUseCase:
    """Links or provisions a dependent account under a primary Family plan account."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    password_hasher: PasswordHasherPort | None = None
    family_plan_service: FamilyPlanService = field(default_factory=FamilyPlanService)

    def _link_existing(
        self,
        primary_user: User,
        dependent_user_id: int,
        plan: Plan,
    ) -> User:
        dependent_user = self.user_repo.find_by_id(dependent_user_id)
        if not dependent_user:
            raise EntityNotFoundError(f"Dependent user {dependent_user_id} not found.")

        if dependent_user.primary_account_id == primary_user.user_id:
            return dependent_user

        if primary_user.user_id is None:
            raise EntityNotFoundError("Primary user has no valid identifier.")
        current_dependents = self.user_repo.list_dependents(primary_user.user_id)
        self.family_plan_service.link_dependent(
            primary_user=primary_user,
            dependent_user=dependent_user,
            plan=plan,
            current_dependents_count=len(current_dependents),
        )
        return self.user_repo.save(dependent_user)

    def _provision_dependent(
        self,
        primary_user: User,
        plan: Plan,
        email: str,
        password: str,
        display_name: str | None,
        birth_date: str | None,
    ) -> User:
        if primary_user.user_id is None:
            raise EntityNotFoundError("Primary user has no valid identifier.")
        current_dependents = self.user_repo.list_dependents(primary_user.user_id)
        if len(current_dependents) + 1 >= plan.max_profiles:
            raise BusinessRuleViolationError(
                f"Limite máximo de {plan.max_profiles} perfis do plano Família atingido."
            )

        email_clean = email.strip().lower()
        if self.user_repo.find_by_email(email_clean):
            raise DuplicateEntityError(f"E-mail {email_clean} já está em uso.")

        birth_date_str = birth_date.strip() if birth_date else None
        age = 0
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

        if self.password_hasher is not None:
            pw_hash = self.password_hasher.hash_password(password)
        else:
            pw_hash = _default_hash_password(password)

        new_dependent = User(
            user_id=None,
            email=email_clean,
            password_hash=pw_hash,
            display_name=(display_name or "").strip(),
            age=age,
            plan_id=primary_user.plan_id,
            primary_account_id=primary_user.user_id,
            birth_date=birth_date_str,
        )
        return self.user_repo.save(new_dependent)

    def execute(
        self,
        primary_user_id: int,
        dependent_user_id: int | None = None,
        *,
        command: AddFamilyMemberCommand | None = None,
        email: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
        birth_date: str | None = None,
    ) -> User:
        if command is not None:
            primary_user_id = command.primary_user_id
            email = command.email or email
            password = command.password or password
            display_name = command.display_name or display_name
            birth_date = command.birth_date or birth_date
            if command.dependent_user_id is not None:
                dependent_user_id = command.dependent_user_id

        primary_user = self.user_repo.find_by_id(primary_user_id)
        if not primary_user or primary_user.user_id is None:
            raise EntityNotFoundError(f"Primary user {primary_user_id} not found.")

        plan = self.plan_repo.find_by_id(primary_user.plan_id)
        if not plan:
            raise EntityNotFoundError(f"Plan with ID {primary_user.plan_id} not found.")

        if not plan.allows_dependents:
            raise PermissionDeniedError(
                "Current plan does not support adding family members."
            )

        if primary_user.primary_account_id is not None:
            raise PermissionDeniedError(
                "A dependent user cannot manage family members."
            )

        if dependent_user_id is not None and not (email and password):
            return self._link_existing(primary_user, dependent_user_id, plan)

        if email and password:
            return self._provision_dependent(
                primary_user=primary_user,
                plan=plan,
                email=email,
                password=password,
                display_name=display_name,
                birth_date=birth_date,
            )

        raise BusinessRuleViolationError("Dados do membro da família incompletos.")
