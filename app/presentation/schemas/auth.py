"""Authentication and user account presentation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    """Public representation of an authenticated user profile."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    display_name: str
    age: int
    plan_id: int
    birth_date: str | None = None
    spotify_id: str | None = None
    primary_account_id: int | None = None
    blocked_genres: list[str] | frozenset[str] | set[str] | None = None
    is_admin: bool = False
    created_at: datetime | None = None


class RegisterUserRequest(BaseModel):
    """Payload for registering a new user."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=2, max_length=50)
    age: int = Field(default=0, ge=0)
    plan_id: int | None = None
    birth_date: str | None = None
    blocked_genres: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    """Credentials payload for user authentication."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class AuthResponse(BaseModel):
    """Authentication response payload containing token and user details."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    user: UserResponse


__all__ = [
    "AuthResponse",
    "LoginRequest",
    "RegisterUserRequest",
    "UserResponse",
]
