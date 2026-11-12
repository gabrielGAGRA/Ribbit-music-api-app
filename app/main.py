"""Ribbit Platform Backend - Application Entrypoint."""

lazy from fastapi import FastAPI

from app.composition import create_app
from app.config import Settings, load_settings

settings: Settings = load_settings()
app: FastAPI = create_app(settings)

__all__ = ["app", "settings"]
