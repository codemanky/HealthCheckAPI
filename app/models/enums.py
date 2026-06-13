"""Enumerations for health status and component types."""

from enum import StrEnum


class HealthStatus(StrEnum):
    """Possible health states for a component or the overall system."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(StrEnum):
    """Logical category of a system component."""

    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    GATEWAY = "gateway"
    EXTERNAL = "external"
    CUSTOM = "custom"
