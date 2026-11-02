"""Port interface for authentication token generation and decoding."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TokenServicePort(Protocol):
    """Protocol for generating and validating bearer access tokens."""

    def create_access_token(
        self,
        user_id: int,
        is_admin: bool = False,
        expires_in_seconds: int | None = None,
    ) -> str:
        """Encodes an access token for a given user."""
        ...

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Decodes and validates a bearer token, returning its claims."""
        ...


__all__ = ["TokenServicePort"]
