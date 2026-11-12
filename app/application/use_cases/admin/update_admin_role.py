"""Use case for updating user administrator role."""

from dataclasses import dataclass

from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
lazy from app.application.dtos.admin_dtos import UpdateAdminRoleCommand
lazy from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class UpdateAdminRoleUseCase:
    """Updates user is_admin status while preventing administrator self-demotion."""

    user_repo: UserRepositoryPort
    eligible_emails: tuple[str, ...] = ()
    audit_log_repo: AuditLogRepositoryPort | None = None

    def execute(
        self,
        command: UpdateAdminRoleCommand | None = None,
        *,
        admin_id: int | None = None,
        target_user_id: int | None = None,
        is_admin: bool | None = None,
    ) -> User:
        if command is not None:
            effective_admin_id = command.admin_id
            effective_target_id = command.target_user_id
            effective_is_admin = command.is_admin
        else:
            if admin_id is None or target_user_id is None or is_admin is None:
                raise ValueError("admin_id, target_user_id, and is_admin are required.")
            effective_admin_id = admin_id
            effective_target_id = target_user_id
            effective_is_admin = is_admin

        if effective_admin_id == effective_target_id and not effective_is_admin:
            raise BusinessRuleViolationError("Administrator cannot revoke own access.")

        user = self.user_repo.find_by_id(effective_target_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {effective_target_id} not found.")

        if effective_is_admin:
            normalized_eligible = {e.strip().lower() for e in self.eligible_emails}
            if user.email.strip().lower() not in normalized_eligible:
                raise BusinessRuleViolationError(
                    f"User {user.email} is not eligible for administrative privileges."
                )

        user.is_admin = effective_is_admin
        saved_user = self.user_repo.save(user)
        if self.audit_log_repo is not None:
            self.audit_log_repo.log_event(
                f"ADMIN_ROLE_UPDATED:{user.email}:{effective_is_admin}", "OK"
            )
        return saved_user


__all__ = ["UpdateAdminRoleUseCase"]
