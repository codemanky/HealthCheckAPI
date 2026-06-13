"""Factory that selects the correct health check strategy for a component."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.models.schemas import ComponentInput
from app.services.checks.base import BaseHealthCheck
from app.services.checks.http_check import HttpHealthCheck
from app.services.checks.registry import DEFAULT_CHECK_REGISTRY
from app.services.checks.simulated_check import SimulatedHealthCheck
from app.services.checks.tcp_check import TcpHealthCheck


def get_check_strategy(
    component: ComponentInput,
    settings: Settings | None = None,
) -> BaseHealthCheck:
    """Return the appropriate health check strategy for a component.

    Routing logic:
    1. Parse the endpoint URL scheme and hostname.
    2. If hostname ends with ``.sim`` → SimulatedHealthCheck.
    3. Otherwise, route on scheme:
       - ``http`` / ``https``  → HttpHealthCheck
       - ``tcp``               → TcpHealthCheck

    Timeout is derived from the component type's registry entry.

    Args:
        component: The component to select a strategy for.
        settings: Application settings (uses singleton if not provided).

    Returns:
        A concrete ``BaseHealthCheck`` instance ready to call ``.check()``.

    Raises:
        ValueError: If the endpoint scheme is unsupported.
    """
    cfg = settings or get_settings()
    parsed = urlparse(component.endpoint)
    hostname = parsed.hostname or ""

    # Determine timeout from type registry
    registry_entry = DEFAULT_CHECK_REGISTRY.get(component.type)
    timeout_seconds = (
        registry_entry.timeout_ms / 1000
        if registry_entry
        else cfg.default_check_timeout_seconds
    )

    # Simulated endpoint detection
    if hostname.endswith(cfg.sim_hostname_suffix):
        return SimulatedHealthCheck(
            timeout=timeout_seconds,
            max_retries=cfg.check_max_retries,
            retry_base_delay=cfg.check_retry_base_delay_seconds,
        )

    # Real endpoint: route on URL scheme
    match parsed.scheme:
        case "http" | "https":
            return HttpHealthCheck(
                timeout=timeout_seconds,
                max_retries=cfg.check_max_retries,
                retry_base_delay=cfg.check_retry_base_delay_seconds,
            )
        case "tcp":
            return TcpHealthCheck(
                timeout=timeout_seconds,
                max_retries=cfg.check_max_retries,
                retry_base_delay=cfg.check_retry_base_delay_seconds,
            )
        case _:
            raise ValueError(
                f"Unsupported endpoint scheme '{parsed.scheme}' "
                f"for component '{component.id}'. "
                "Supported schemes: http, https, tcp"
            )
