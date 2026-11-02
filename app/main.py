"""Ribbit Platform Backend - Application Entrypoint."""

from app.composition import create_app
from app.config import load_settings

settings = load_settings()
app = create_app(settings)

__all__ = ["app"]
