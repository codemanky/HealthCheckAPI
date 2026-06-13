"""Enumerations for health status and component types."""

from enum import Enum


class HealthStatus(str, Enum):
    """Possible health states for a component or the overall system."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Logical category of a system component."""

    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    GATEWAY = "gateway"
    EXTERNAL = "external"
    CUSTOM = "custom"
