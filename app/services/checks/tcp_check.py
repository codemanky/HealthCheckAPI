"""TCP connectivity health check strategy using asyncio streams."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

from app.models.enums import HealthStatus
from app.models.schemas import ComponentInput
from app.services.checks.base import BaseHealthCheck


class TcpHealthCheck(BaseHealthCheck):
    """Checks component health by opening a TCP connection to host:port.

    The endpoint must follow the format ``tcp://host:port`` (path is ignored
    for real checks — it is only meaningful for simulated endpoints).

    Status mapping:
    - Connection established  → HEALTHY
    - Connection refused      → UNHEALTHY
    - Timeout                 → UNHEALTHY (handled by BaseHealthCheck)
    """

    async def _perform_check(self, component: ComponentInput) -> tuple[HealthStatus, str]:
        """Open a TCP connection and close it immediately.

        Args:
            component: Component whose ``tcp://host:port`` endpoint to probe.

        Returns:
            (status, message) tuple.
        """
        parsed = urlparse(component.endpoint)
        host = parsed.hostname or ""
        port = parsed.port

        if not host or not port:
            return (
                HealthStatus.UNHEALTHY,
                f"Cannot parse host/port from endpoint '{component.endpoint}'",
            )

        start = time.monotonic()
        reader, writer = await asyncio.open_connection(host, port)
        elapsed_ms = (time.monotonic() - start) * 1000
        writer.close()
        await writer.wait_closed()

        return (
            HealthStatus.HEALTHY,
            f"TCP connection to {host}:{port} established ({elapsed_ms:.0f}ms)",
        )
