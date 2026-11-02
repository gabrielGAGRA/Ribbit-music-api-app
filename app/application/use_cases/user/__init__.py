"""User, profile, and family plan use cases."""

from app.application.use_cases.user.add_family_member import (
    AddFamilyMemberUseCase,
)
from app.application.use_cases.user.cancel_subscription_plan import (
    CancelSubscriptionPlanUseCase,
)
from app.application.use_cases.user.change_subscription_plan import (
    ChangeSubscriptionPlanUseCase,
)
from app.application.use_cases.user.change_track_interaction import (
    ChangeTrackInteractionUseCase,
)
from app.application.use_cases.user.delete_user_account import (
    DeleteUserAccountUseCase,
)
from app.application.use_cases.user.get_annual_stats import (
    GetAnnualListeningStatsUseCase,
)
from app.application.use_cases.user.get_user_profile import (
    GetUserProfileUseCase,
)
from app.application.use_cases.user.link_spotify_account import (
    LinkSpotifyAccountUseCase,
)
from app.application.use_cases.user.list_blocked_genres import (
    ListBlockedGenresUseCase,
)
from app.application.use_cases.user.list_family_members import (
    ListFamilyMembersUseCase,
)
from app.application.use_cases.user.list_plans import ListPlansUseCase
from app.application.use_cases.user.list_user_interactions import (
    ListUserInteractionsUseCase,
)
from app.application.use_cases.user.remove_family_member import (
    RemoveFamilyMemberUseCase,
)
from app.application.use_cases.user.update_blocked_genres import (
    UpdateBlockedGenresUseCase,
)
from app.application.use_cases.user.update_profile import UpdateProfileUseCase

__all__ = [
    "AddFamilyMemberUseCase",
    "CancelSubscriptionPlanUseCase",
    "ChangeSubscriptionPlanUseCase",
    "ChangeTrackInteractionUseCase",
    "DeleteUserAccountUseCase",
    "GetAnnualListeningStatsUseCase",
    "GetUserProfileUseCase",
    "LinkSpotifyAccountUseCase",
    "ListBlockedGenresUseCase",
    "ListFamilyMembersUseCase",
    "ListPlansUseCase",
    "ListUserInteractionsUseCase",
    "RemoveFamilyMemberUseCase",
    "UpdateBlockedGenresUseCase",
    "UpdateProfileUseCase",
]
