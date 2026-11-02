"""Dependency provider utilities resolving components from the application container."""

from typing import cast
lazy from collections.abc import Callable

from fastapi import Request

lazy from app.composition import Container


def get_container(request: Request) -> Container:
    """Retrieves the composition container attached to the application state."""
    return cast("Container", request.app.state.container)


def provide[T](dependency_type: type[T]) -> Callable[[Request], T]:
    """Factory creating FastAPI dependencies that resolve a component by its type."""

    def _dependency(request: Request) -> T:
        return get_container(request).resolve(dependency_type)

    return _dependency


__all__ = ["get_container", "provide"]
