"""FastAPI dependency injection providers."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.health_checker import HealthCheckerService
from app.services.visualizer import DAGVisualizer


@lru_cache
def get_health_checker() -> HealthCheckerService:
    """Return a cached HealthCheckerService singleton."""
    return HealthCheckerService(settings=get_settings())


@lru_cache
def get_visualizer() -> DAGVisualizer:
    """Return a cached DAGVisualizer singleton."""
    return DAGVisualizer()
