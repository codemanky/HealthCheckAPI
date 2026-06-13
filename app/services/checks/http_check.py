"""HTTP health check strategy using httpx."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.models.enums import HealthStatus
from app.services.checks.base import BaseHealthCheck

if TYPE_CHECKING:
    from app.models.schemas import ComponentInput

# Latency threshold above which a 2xx response is considered DEGRADED
_DEGRADED_LATENCY_MS = 500.0


class HttpHealthCheck(BaseHealthCheck):
    """Checks component health by issuing an HTTP GET to its endpoint.

    Status mapping:
    - 2xx and latency < threshold  → HEALTHY
    - 2xx but latency ≥ threshold  → DEGRADED
    - Non-2xx or connection error  → UNHEALTHY
    """

    async def _perform_check(self, component: ComponentInput) -> tuple[HealthStatus, str]:
        """Issue an HTTP GET and evaluate the response.

        Args:
            component: Component whose endpoint to probe.

        Returns:
            (status, message) tuple.
        """
        import time

        async with httpx.AsyncClient(follow_redirects=True) as client:
            start = time.monotonic()
            response = await client.get(component.endpoint)
            elapsed_ms = (time.monotonic() - start) * 1000

        if response.is_success:
            if elapsed_ms >= _DEGRADED_LATENCY_MS:
                return (
                    HealthStatus.DEGRADED,
                    f"HTTP {response.status_code} — response slow ({elapsed_ms:.0f}ms ≥ {_DEGRADED_LATENCY_MS:.0f}ms threshold)",
                )
            return (
                HealthStatus.HEALTHY,
                f"HTTP {response.status_code} OK ({elapsed_ms:.0f}ms)",
            )

        return (
            HealthStatus.UNHEALTHY,
            f"HTTP {response.status_code} — endpoint returned non-success status",
        )
