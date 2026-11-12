"""Use case for registering a platform administrator."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
lazy from app.application.dtos.admin_dtos import RegisterAdministratorCommand
lazy from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class RegisterAdministratorUseCase:
    """Registers a new platform user with administrator privileges."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    password_hasher: PasswordHasherPort
    audit_log_repo: AuditLogRepositoryPort | None = None
    eligible_emails: tuple[str, ...] = ()

    def execute(self, command: RegisterAdministratorCommand) -> User:
        email = command.email.strip().lower()
        normalized_eligible = {e.strip().lower() for e in self.eligible_emails}
        if email not in normalized_eligible:
            raise BusinessRuleViolationError(
                f"Email {command.email} is not eligible for administrative privileges."
            )

        existing = self.user_repo.find_by_email(email)
        if existing:
            raise DuplicateEntityError(f"Email {email} is already in use.")

        free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
        if not free_plan or free_plan.plan_id is None:
            raise EntityNotFoundError("Default Free plan not found.")

        hashed_password = self.password_hasher.hash_password(command.password)
        admin_user = User(
            user_id=None,
            email=email,
            password_hash=hashed_password,
            display_name=command.display_name.strip(),
            age=command.age,
            plan_id=free_plan.plan_id,
            is_admin=True,
            birth_date=command.birth_date,
        )
        saved_user = self.user_repo.save(admin_user)
        if self.audit_log_repo is not None:
            self.audit_log_repo.log_event(f"ADMIN_REGISTERED:{email}", "OK")
        return saved_user


__all__ = ["RegisterAdministratorUseCase"]
