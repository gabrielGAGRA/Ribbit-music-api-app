"""Domain model representing a platform user."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import ClassVar, Self
lazy from collections.abc import Iterable

lazy from app.domain.models.track import Track


def _genre_tokens(genre: str) -> tuple[str, ...]:
    normalized = "".join(
        character if character.isalnum() else " " for character in genre.casefold()
    )
    return tuple(normalized.split())


@dataclass(slots=True, kw_only=True, eq=False)
class User:
    MIN_ADULT_AGE: ClassVar[int] = 18
    MINOR_RESTRICTED_GENRE_TERMS: ClassVar[frozenset[str]] = frozenset(
        {"funk", "hip hop", "rap", "trap"}
    )

    user_id: int | None = None
    email: str
    password_hash: str
    display_name: str
    age: int
    plan_id: int
    spotify_id: str | None = None
    primary_account_id: int | None = None
    blocked_genres: frozenset[str] = frozenset()
    favorite_genres: frozenset[str] = frozenset()
    preferred_theme: str = "light"
    is_admin: bool = False
    created_at: datetime | None = None
    birth_date: str | None = None

    @staticmethod
    def _normalize_genre(genre: str) -> str:
        return genre.strip().casefold()

    @staticmethod
    def _genre_tokens(genre: str) -> tuple[str, ...]:
        normalized = "".join(
            character if character.isalnum() else " " for character in genre.casefold()
        )
        return tuple(normalized.split())

    def __post_init__(self) -> None:
        if not self.email.strip():
            raise ValueError("Email cannot be blank.")
        if not self.display_name.strip():
            raise ValueError("Display name cannot be blank.")
        if self.age < 0:
            raise ValueError("Age cannot be negative.")
        if self.birth_date is not None:
            self.birth_date = self.birth_date.strip() or None
        self.blocked_genres = frozenset(
            self._normalize_genre(genre)
            for genre in self.blocked_genres
            if genre.strip()
        )
        self.favorite_genres = frozenset(
            self._normalize_genre(genre)
            for genre in self.favorite_genres
            if genre.strip()
        )
        self.preferred_theme = self._normalize_theme(self.preferred_theme)

    @staticmethod
    def _normalize_genre(genre: str) -> str:
        return genre.strip().casefold()

    @staticmethod
    def _normalize_theme(theme: str | None) -> str:
        normalized = (theme or "light").strip().casefold()
        if normalized not in {"light", "dark"}:
            raise ValueError("Preferred theme must be either 'light' or 'dark'.")
        return normalized

    def current_age(self, today: date | None = None) -> int:
        if not self.birth_date:
            return self.age
        try:
            bdate = date.fromisoformat(self.birth_date)
        except ValueError, TypeError:
            return self.age
        ref_date = today or datetime.now(UTC).date()
        return (
            ref_date.year
            - bdate.year
            - ((ref_date.month, ref_date.day) < (bdate.month, bdate.day))
        )

    @staticmethod
    def is_age_minor(age: int) -> bool:
        return age < User.MIN_ADULT_AGE

    def is_minor(self) -> bool:
        return self.is_age_minor(self.current_age())

    @property
    def is_adult(self) -> bool:
        return not self.is_minor()

    idade_atual = current_age
    eh_menor_de_idade = is_minor
    idade_indica_menor = is_age_minor

    def can_listen(self, track: Track) -> bool:
        genre = self._normalize_genre(track.genre)
        return (
            not self.is_track_restricted_for_minor(track)
            and genre not in self.blocked_genres
        )

    def is_track_restricted_for_minor(self, track: Track) -> bool:
        if not self.is_minor():
            return False
        if track.explicit:
            return True

        genre_tokens = self._genre_tokens(track.genre)
        return any(
            genre_tokens[index : index + len(term_tokens)] == term_tokens
            for term_tokens in (
                tuple(term.split()) for term in self.MINOR_RESTRICTED_GENRE_TERMS
            )
            for index in range(len(genre_tokens) - len(term_tokens) + 1)
        )

    def link_primary_account(self, primary_account_id: int) -> Self:
        if self.user_id is not None and primary_account_id == self.user_id:
            raise ValueError("Cannot link user account to itself as primary account.")
        self.primary_account_id = primary_account_id
        return self

    def promote_to_admin(self) -> Self:
        self.is_admin = True
        return self

    def change_plan(self, plan_id: int) -> Self:
        self.plan_id = plan_id
        return self

    def unlink_primary_account(self, fallback_plan_id: int) -> Self:
        self.primary_account_id = None
        self.plan_id = fallback_plan_id
        return self

    def link_spotify(self, spotify_id: str) -> Self:
        cleaned = spotify_id.strip()
        if not cleaned:
            raise ValueError("Spotify ID cannot be blank.")
        self.spotify_id = cleaned
        return self

    def update_blocked_genres(self, genres: Iterable[str]) -> Self:
        self.blocked_genres = frozenset(
            self._normalize_genre(genre) for genre in genres if genre.strip()
        )
        return self

    def update_favorite_genres(self, genres: Iterable[str]) -> Self:
        self.favorite_genres = frozenset(
            self._normalize_genre(genre) for genre in genres if genre.strip()
        )
        return self

    def update_preferred_theme(self, theme: str) -> Self:
        self.preferred_theme = self._normalize_theme(theme)
        return self

    def update_profile(
        self,
        *,
        display_name: str | None = None,
        password_hash: str | None = None,
    ) -> Self:
        if display_name is not None:
            cleaned_name = display_name.strip()
            if not cleaned_name:
                raise ValueError("Display name cannot be blank.")
            self.display_name = cleaned_name
        if password_hash is not None:
            if not password_hash.strip():
                raise ValueError("Password hash cannot be blank.")
            self.password_hash = password_hash
        return self

    DEFAULT_GENRE_WEIGHT: ClassVar[float] = 1.0

    def is_favorite_genre(self, track: Track) -> bool:
        normalized_favorites = {
            self._normalize_genre(genre)
            for genre in self.favorite_genres
            if genre and genre.strip()
        }
        if not normalized_favorites or not track.genre.strip():
            return False

        track_genre = self._normalize_genre(track.genre)
        if track_genre in normalized_favorites:
            return True

        genre_tokens = self._genre_tokens(track.genre)
        if not genre_tokens:
            return False

        for favorite in normalized_favorites:
            fav_tokens = self._genre_tokens(favorite)
            if fav_tokens and any(
                genre_tokens[index : index + len(fav_tokens)] == fav_tokens
                for index in range(len(genre_tokens) - len(fav_tokens) + 1)
            ):
                return True
        return False

    def recommendation_weight(
        self,
        track: Track,
        *,
        favorite_multiplier: float | None = None,
    ) -> float:
        if not self.can_listen(track):
            return 0.0
        if self.is_favorite_genre(track):
            return (
                DEFAULT_FAVORITE_WEIGHT_MULTIPLIER
                if favorite_multiplier is None
                else favorite_multiplier
            )
        return self.DEFAULT_GENRE_WEIGHT


DEFAULT_FAVORITE_WEIGHT_MULTIPLIER: float = 3.0
