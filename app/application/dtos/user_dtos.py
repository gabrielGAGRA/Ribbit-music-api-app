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
        if item == "user":
            return self.user
        if item == "plan":
            return self.plan
        if item == "recent_interactions":
            return self.recent_interactions
        raise KeyError(item)


@dataclass(slots=True, frozen=True, kw_only=True)
class GenreStat:
    genre: str
    likes: int
    superlikes: int
    dislikes: int
    total_positive: int


@dataclass(slots=True, frozen=True, kw_only=True)
class ArtistStat:
    artist: str
    likes: int
    superlikes: int
    dislikes: int
    total_positive: int


@dataclass(slots=True, frozen=True, kw_only=True)
class YearlyInteractionStat:
    year: int
    likes: int
    superlikes: int
    dislikes: int
    total: int


@dataclass(slots=True, frozen=True, kw_only=True)
class MonthlyInteractionStat:
    month: int
    likes: int
    superlikes: int
    dislikes: int
    total: int


@dataclass(slots=True, frozen=True, kw_only=True)
class ReleaseYearStat:
    release_year: int
    likes: int
    superlikes: int
    total_positive: int


@dataclass(slots=True, frozen=True, kw_only=True)
class SourceStat:
    source: str
    likes: int
    superlikes: int
    dislikes: int
    total: int


@dataclass(slots=True, frozen=True, kw_only=True)
class AnnualStatsResult:
    user_id: int
    year: int | None = None
    available_years: list[int] = field(default_factory=list)
    total_interactions: int = 0
    total_likes: int = 0
    total_superlikes: int = 0
    total_dislikes: int = 0
    positive_rate: float = 0.0
    top_genres: list[GenreStat] = field(default_factory=list)
    top_artists: list[ArtistStat] = field(default_factory=list)
    by_interaction_year: list[YearlyInteractionStat] = field(default_factory=list)
    by_month: list[MonthlyInteractionStat] = field(default_factory=list)
    by_release_year: list[ReleaseYearStat] = field(default_factory=list)
    by_source: list[SourceStat] = field(default_factory=list)
    total_reviews: int = 0
    average_rating: float = 0.0
    total_playlists: int = 0
    total_jams_participated: int = 0


__all__ = [
    "AddFamilyMemberCommand",
    "AnnualStatsResult",
    "ArtistStat",
    "GenreStat",
    "MonthlyInteractionStat",
    "ReleaseYearStat",
    "SourceStat",
    "UpdateProfileCommand",
    "UserProfileResult",
    "YearlyInteractionStat",
]
