"""Data transfer objects for authentication actions."""

from dataclasses import dataclass
from typing import Any

lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True, kw_only=True)
class RegisterUserCommand:
    email: str
    password: str
    display_name: str
    age: int | None = None
    plan_id: int | None = None
    birth_date: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class AuthenticateUserCommand:
    email: str
    password: str


@dataclass(slots=True, frozen=True, kw_only=True)
class AuthenticateAdminCommand:
    email: str
    password: str


@dataclass(slots=True, frozen=True, kw_only=True)
class AuthResult:
    user: User
    access_token: str
    token_type: str = "bearer"  # noqa: S105

    def __getattr__(self, item: str) -> Any:
        return getattr(self.user, item)


__all__ = [
    "AuthResult",
    "AuthenticateAdminCommand",
    "AuthenticateUserCommand",
    "RegisterUserCommand",
]
