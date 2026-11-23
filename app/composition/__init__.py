"""Composition package exporting container and FastAPI application factory."""

from app.composition.app_factory import create_app
from app.composition.container import Container, build_container

__all__ = ["Container", "build_container", "create_app"]
