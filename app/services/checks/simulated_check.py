"""Simulated health check strategy for .sim endpoints.

Components with a ``.sim`` hostname suffix use this strategy. The path
and query string in the endpoint URL control the simulated behaviour:

    http://api-gateway.sim/healthy           → always HEALTHY (50–200ms)
    http://api-gateway.sim/unhealthy         → always UNHEALTHY (50–200ms)
    http://api-gateway.sim/degraded          → always DEGRADED (200–500ms)
    tcp://cache.sim:6379/flaky?rate=0.3      → UNHEALTHY 30% of the time
    http://analytics.sim/slow?latency=2000   → HEALTHY after 2000ms delay
    http://gateway.sim/timeout               → simulates a timeout error
"""

from __future__ import annotations

import asyncio
import random
from urllib.parse import parse_qs, urlparse

from app.models.enums import HealthStatus
from app.models.schemas import ComponentInput
from app.services.checks.base import BaseHealthCheck


class SimulatedHealthCheck(BaseHealthCheck):
    """Returns a deterministic or randomised health result without making
    any real network connection.

    The endpoint path (``/healthy``, ``/unhealthy``, etc.) and optional
    query parameters drive the behaviour.
    """

    async def _perform_check(self, component: ComponentInput) -> tuple[HealthStatus, str]:
        """Simulate a health check based on the endpoint path.

        Args:
            component: Component with a .sim endpoint.

        Returns:
            (status, message) tuple.
        """
        parsed = urlparse(component.endpoint)
        path = parsed.path.rstrip("/").lower() or "/healthy"
        query = parse_qs(parsed.query)

        match path:
            case "/healthy":
                await self._jitter(50, 200)
                return HealthStatus.HEALTHY, "Simulated: component is healthy"

            case "/unhealthy":
                await self._jitter(50, 200)
                return HealthStatus.UNHEALTHY, "Simulated: component is unhealthy"

            case "/degraded":
                await self._jitter(200, 500)
                return HealthStatus.DEGRADED, "Simulated: component is degraded"

            case "/flaky":
                failure_rate = float(query.get("rate", ["0.5"])[0])
                await self._jitter(50, 300)
                if random.random() < failure_rate:
                    return (
                        HealthStatus.UNHEALTHY,
                        f"Simulated: flaky component failed (rate={failure_rate:.0%})",
                    )
                return (
                    HealthStatus.HEALTHY,
                    f"Simulated: flaky component passed (rate={failure_rate:.0%})",
                )

            case "/slow":
                latency_ms = float(query.get("latency", ["2000"])[0])
                await asyncio.sleep(latency_ms / 1000)
                return (
                    HealthStatus.DEGRADED,
                    f"Simulated: slow component responded in {latency_ms:.0f}ms",
                )

            case "/timeout":
                # Sleep longer than any reasonable timeout so BaseHealthCheck catches it
                await asyncio.sleep(3600)
                return HealthStatus.UNHEALTHY, "Simulated: timeout (unreachable)"

            case _:
                return (
                    HealthStatus.UNKNOWN,
                    f"Simulated: unrecognised path '{path}'",
                )

    @staticmethod
    async def _jitter(min_ms: int, max_ms: int) -> None:
        """Sleep for a random duration to simulate realistic network latency."""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)
