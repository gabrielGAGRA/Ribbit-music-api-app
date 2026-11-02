"""Data transfer objects for users, profiles, and statistics."""

from dataclasses import dataclass, field
from typing import Any

lazy from app.domain.models.interaction import Interaction
lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True, kw_only=True)
class UpdateProfileCommand:
    user_id: int
    display_name: str | None = None
    new_password: str | None = None
    current_password: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class AddFamilyMemberCommand:
    primary_user_id: int
    email: str | None = None
    password: str | None = None
    display_name: str | None = None
    birth_date: str | None = None
    dependent_user_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class UserProfileResult:
    user: User
    plan: Plan
    recent_interactions: list[Interaction] = field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        if item in ("user", "usuario"):
            return self.user
        if item in ("plan", "plano"):
            return self.plan
        if item in (
            "recent_interactions",
            "interacoes_recentes",
            "ultimas_interacoes",
        ):
            return self.recent_interactions
        raise KeyError(item)


@dataclass(slots=True, frozen=True, kw_only=True)
class AnnualStatsResult:
    user_id: int
    estimated_listening_hours: float
    total_likes: int
    top_genres: list[str]
    top_artists: list[str]


__all__ = [
    "AddFamilyMemberCommand",
    "AnnualStatsResult",
    "UpdateProfileCommand",
    "UserProfileResult",
]
