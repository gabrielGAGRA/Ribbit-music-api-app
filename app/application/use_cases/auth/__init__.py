"""Authentication use cases."""

from app.application.use_cases.auth.authenticate_admin import (
    AuthenticateAdminUseCase,
)
from app.application.use_cases.auth.authenticate_user import (
    AuthenticateUserUseCase,
)
from app.application.use_cases.auth.authenticate_with_google import (
    AuthenticateWithGoogleUseCase,
)
from app.application.use_cases.auth.complete_google_oauth import (
    CompleteGoogleOAuthUseCase,
)
from app.application.use_cases.auth.get_google_authorize_url import (
    GetGoogleAuthorizeUrlUseCase,
)
from app.application.use_cases.auth.register_user import RegisterUserUseCase

__all__ = [
    "AuthenticateAdminUseCase",
    "AuthenticateUserUseCase",
    "AuthenticateWithGoogleUseCase",
    "CompleteGoogleOAuthUseCase",
    "GetGoogleAuthorizeUrlUseCase",
    "RegisterUserUseCase",
]
