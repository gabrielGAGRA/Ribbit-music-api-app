"""Security port for password hashing and verification."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordHasherPort(Protocol):
    """Abstract port for cryptographic password operations."""

    def hash_password(self, password: str) -> str:
        """Computes a secure hash for the given plain text password."""
        ...

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verifies if the given plain text password matches the stored hash."""
        ...
