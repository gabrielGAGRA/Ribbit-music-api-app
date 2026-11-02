"""Use case for updating user administrator role."""

from dataclasses import dataclass

from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
lazy from app.application.dtos.admin_dtos import UpdateAdminRoleCommand
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class UpdateAdminRoleUseCase:
    """Updates user is_admin status while preventing administrator self-demotion."""

    user_repo: UserRepositoryPort

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
            raise BusinessRuleViolationError(
                "Administrador não pode revogar o próprio acesso."
            )

        user = self.user_repo.find_by_id(effective_target_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {effective_target_id} not found.")

        user.is_admin = effective_is_admin
        return self.user_repo.save(user)


__all__ = ["UpdateAdminRoleUseCase"]
