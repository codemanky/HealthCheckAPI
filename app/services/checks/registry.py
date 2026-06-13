"""Default check configuration registry mapping ComponentType to check config."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ComponentType


@dataclass(frozen=True)
class CheckConfig:
    """Default check parameters for a component type.

    Args:
        protocol: Default protocol to use if endpoint scheme is absent.
        timeout_ms: Default timeout for this component type in milliseconds.
        default_port: Default port (informational; used for TCP checks).
    """

    protocol: str
    timeout_ms: int
    default_port: int | None = None


DEFAULT_CHECK_REGISTRY: dict[ComponentType, CheckConfig] = {
    ComponentType.SERVICE: CheckConfig(protocol="http", timeout_ms=3000),
    ComponentType.DATABASE: CheckConfig(protocol="tcp", timeout_ms=5000, default_port=5432),
    ComponentType.CACHE: CheckConfig(protocol="tcp", timeout_ms=2000, default_port=6379),
    ComponentType.QUEUE: CheckConfig(protocol="tcp", timeout_ms=3000, default_port=5672),
    ComponentType.GATEWAY: CheckConfig(protocol="http", timeout_ms=3000),
    ComponentType.EXTERNAL: CheckConfig(protocol="http", timeout_ms=5000),
    ComponentType.CUSTOM: CheckConfig(protocol="http", timeout_ms=3000),
}
