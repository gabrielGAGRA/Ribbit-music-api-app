"""Domain services module for cross-aggregate business logic."""

from app.domain.services.country_names import (
    COUNTRY_CODE_TO_PT,
    country_matches,
    expand_country_terms,
    translate_country_to_pt,
)
from app.domain.services.family_plan_service import FamilyPlanService
from app.domain.services.genre_names import (
    CATALOG_GENRES,
    GENRE_CATALOG_DICT,
    GENRE_DB_TO_CANONICAL,
    expand_genre_aliases,
    expand_genre_db_values,
    genre_matches_preference,
)
from app.domain.services.subscription_analytics_service import (
    RevenueBreakdown,
    SubscriptionAnalyticsService,
)

__all__ = [
    "CATALOG_GENRES",
    "COUNTRY_CODE_TO_PT",
    "GENRE_CATALOG_DICT",
    "GENRE_DB_TO_CANONICAL",
    "FamilyPlanService",
    "RevenueBreakdown",
    "SubscriptionAnalyticsService",
    "country_matches",
    "expand_country_terms",
    "expand_genre_aliases",
    "expand_genre_db_values",
    "genre_matches_preference",
    "translate_country_to_pt",
]
