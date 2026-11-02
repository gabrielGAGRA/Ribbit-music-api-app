"""Use case for updating display name or password of a user."""

from dataclasses import dataclass

from app.domain.exceptions import AuthenticationRequiredError, EntityNotFoundError
lazy from app.application.dtos.user_dtos import UpdateProfileCommand
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.password_hasher import PasswordHasherPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class UpdateProfileUseCase:
    """Updates user profile attributes such as display name and password."""

    user_repo: UserRepositoryPort
    password_hasher: PasswordHasherPort

    def execute(self, command: UpdateProfileCommand) -> User:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        password_hash: str | None = None
        if command.new_password:
            if not command.current_password or not self.password_hasher.verify_password(
                command.current_password, user.password_hash
            ):
                raise AuthenticationRequiredError(
                    "Current password is required and must match."
                )
            password_hash = self.password_hasher.hash_password(command.new_password)

        user.update_profile(
            display_name=command.display_name,
            password_hash=password_hash,
        )

        return self.user_repo.save(user)
