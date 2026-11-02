"""Domain exception hierarchy."""

from typing import Any
lazy from collections.abc import Mapping


class CustomError(Exception):
    def __init__(
        self,
        message: str,
        name: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.name = name or self.__class__.__name__
        self.details: dict[str, Any] = dict(details or {})


class DomainError(CustomError):
    pass


class EntityNotFoundError(DomainError):
    def __init__(
        self,
        message: str | None = None,
        entity_name: str | None = None,
        entity_id: int | str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        ctx = dict(details or {})
        if entity_name:
            ctx["entity_name"] = entity_name
        if entity_id is not None:
            ctx["entity_id"] = entity_id
        default_message = (
            f"Entity '{entity_name}' with id '{entity_id}' not found."
            if entity_name and entity_id is not None
            else "Requested entity was not found."
        )
        super().__init__(message or default_message, details=ctx)


class BusinessRuleViolationError(DomainError):
    def __init__(
        self,
        message: str,
        rule_name: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        ctx = dict(details or {})
        if rule_name:
            ctx["rule_name"] = rule_name
        super().__init__(message, details=ctx)


class DuplicateEntityError(DomainError):
    """The conflicting value is deliberately not recorded: it may be personal data."""

    def __init__(
        self,
        message: str | None = None,
        entity_name: str | None = None,
        field: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        ctx = dict(details or {})
        if entity_name:
            ctx["entity_name"] = entity_name
        if field:
            ctx["field"] = field
        default_message = (
            f"Entity '{entity_name}' with {field} already exists."
            if entity_name and field
            else "Entity already registered."
        )
        super().__init__(message or default_message, details=ctx)


class ExternalServiceError(DomainError):
    """Raised when an external service or provider fails, abstracting transport errors."""

    def __init__(
        self,
        message: str = "External service unavailable or returned an error.",
        service_name: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        ctx = dict(details or {})
        if service_name:
            ctx["service_name"] = service_name
        super().__init__(message, details=ctx)


class SpotifyError(ExternalServiceError):
    """Spotify request failed or answered with an unexpected payload."""

    def __init__(
        self,
        message: str = "Spotify request failed.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, service_name="Spotify", details=details)


class SpotifyAuthError(SpotifyError):
    """Spotify credentials or tokens are missing, expired, or revoked."""


class SpotifyForbiddenError(SpotifyError):
    """Spotify denied access: missing scope, user outside the allowlist, or no Premium."""


class SpotifyQuotaExceededError(SpotifyError):
    """Development-mode quota is exhausted; retrying will not help."""


class AuthenticationRequiredError(DomainError):
    def __init__(
        self,
        message: str = "Authentication required.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class PermissionDeniedError(DomainError):
    def __init__(
        self,
        message: str = "Permission denied.",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


UnauthorizedError = AuthenticationRequiredError
ForbiddenError = PermissionDeniedError

__all__ = [
    "AuthenticationRequiredError",
    "BusinessRuleViolationError",
    "CustomError",
    "DomainError",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "ExternalServiceError",
    "ForbiddenError",
    "PermissionDeniedError",
    "SpotifyAuthError",
    "SpotifyError",
    "SpotifyForbiddenError",
    "SpotifyQuotaExceededError",
    "UnauthorizedError",
]
