"""Presentation layer dependency injection barrel."""

from app.presentation.dependencies.auth import (
    ADMIN_ID_HEADER,
    USER_ID_HEADER,
    get_admin_id,
    get_current_user_id,
    require_admin,
    require_user,
)
from app.presentation.dependencies.container import (
    get_container,
    provide,
)

__all__ = [
    "ADMIN_ID_HEADER",
    "USER_ID_HEADER",
    "get_admin_id",
    "get_container",
    "get_current_user_id",
    "provide",
    "require_admin",
    "require_user",
]
