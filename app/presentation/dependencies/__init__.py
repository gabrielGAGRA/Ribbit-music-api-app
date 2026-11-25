"""Presentation layer dependency injection barrel."""

from app.presentation.dependencies.auth import (
    get_current_user,
    get_current_user_id,
    get_optional_current_user,
    require_admin,
    require_user,
)
from app.presentation.dependencies.container import (
    get_container,
    provide,
    provide_optional,
)

__all__ = [
    "get_container",
    "get_current_user",
    "get_current_user_id",
    "get_optional_current_user",
    "provide",
    "provide_optional",
    "require_admin",
    "require_user",
]
