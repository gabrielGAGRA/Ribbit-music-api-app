"""Domain model representing a subscription plan."""

from dataclasses import InitVar, dataclass, field
from typing import ClassVar, Self


@dataclass(slots=True, kw_only=True, eq=False)
class Plan:
    DEFAULT_FREE_PLAN_NAME: ClassVar[str] = "Free"

    plan_id: int | None = None
    name: str
    initial_monthly_price: InitVar[float]
    initial_max_profiles: InitVar[int] = 1
    _monthly_price: float = field(init=False, repr=False)
    _max_profiles: int = field(init=False, repr=False)

    def __post_init__(
        self, initial_monthly_price: float, initial_max_profiles: int
    ) -> None:
        self.update_price(initial_monthly_price)
        self.update_max_profiles(initial_max_profiles)

    @property
    def monthly_price(self) -> float:
        return self._monthly_price

    @property
    def max_profiles(self) -> int:
        return self._max_profiles

    @property
    def is_paid(self) -> bool:
        return self._monthly_price > 0.0

    @property
    def allows_dependents(self) -> bool:
        return self.is_paid and self._max_profiles > 1

    def can_accommodate(self, total_profiles: int) -> bool:
        return total_profiles <= self._max_profiles

    def can_accommodate_new_dependent(self, current_dependents: int) -> bool:
        """Counts the primary account, current dependents and the new dependent."""
        if not self.allows_dependents:
            return False
        return self.can_accommodate(1 + current_dependents + 1)

    def update_name(self, new_name: str) -> Self:
        cleaned = new_name.strip()
        if not cleaned:
            raise ValueError("Plan name cannot be blank.")
        self.name = cleaned
        return self

    def update_price(self, new_price: float) -> Self:
        if new_price < 0.0:
            raise ValueError("Monthly price cannot be negative.")
        self._monthly_price = new_price
        return self

    def update_max_profiles(self, new_max: int) -> Self:
        if new_max < 1:
            raise ValueError("Max profiles must be at least 1.")
        self._max_profiles = new_max
        return self
