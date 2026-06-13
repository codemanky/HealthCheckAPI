"""Abstract base class for all health check strategies."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import HealthStatus
from app.models.schemas import ComponentHealth, ComponentInput
from app.observability.metrics import CIRCUIT_BREAKER_OPEN_TOTAL
from app.services.checks.circuit_breaker import get_circuit_breaker

logger = get_logger(__name__)


class BaseHealthCheck(ABC):
    """Abstract base for a health check strategy.

    Subclasses implement ``_perform_check`` to perform the actual probe.
    This base class wraps that with timeout enforcement, timing, and
    standard error handling so each strategy only needs to focus on
    the check logic itself.

    Args:
        timeout: Maximum seconds to wait before declaring the check timed out.
    """

    def __init__(
        self,
        timeout: float = 5.0,
        max_retries: int = 0,
        retry_base_delay: float = 0.5,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._settings = get_settings()
        self._circuit_breaker = None
        if self._settings.circuit_breaker_enabled:
            self._circuit_breaker = get_circuit_breaker(
                failure_threshold=self._settings.circuit_breaker_failure_threshold,
                recovery_seconds=self._settings.circuit_breaker_recovery_seconds,
            )

    async def check(
        self,
        component: ComponentInput,
        dependencies: list[str],
    ) -> ComponentHealth:
        """Run the health check with timeout, retries, circuit breaker, and error handling.

        Args:
            component: The component to check.
            dependencies: IDs of this component's direct dependencies.

        Returns:
            A ``ComponentHealth`` result regardless of outcome.
        """
        start = time.monotonic()

        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.allow_request(component.endpoint):
            status = HealthStatus.UNHEALTHY
            message = "Circuit breaker open — skipping check"
            CIRCUIT_BREAKER_OPEN_TOTAL.labels(
                component_id=component.id,
                endpoint=component.endpoint,
            ).inc()
            logger.warning(
                "Circuit breaker prevented request",
                component_id=component.id,
                endpoint=component.endpoint,
            )
        else:
            status = HealthStatus.UNKNOWN
            message = ""

            for attempt in range(1 + self.max_retries):
                try:
                    status, message = await asyncio.wait_for(
                        self._perform_check(component),
                        timeout=self.timeout,
                    )
                    if status != HealthStatus.UNHEALTHY or attempt == self.max_retries:
                        break

                    delay = self.retry_base_delay * (2**attempt)
                    logger.warning(
                        "Health check attempt failed, retrying",
                        component_id=component.id,
                        attempt=attempt + 1,
                        delay_s=delay,
                        error=message,
                    )
                    await asyncio.sleep(delay)
                except TimeoutError:
                    status = HealthStatus.UNHEALTHY
                    message = f"Check timed out after {self.timeout}s"
                    if attempt < self.max_retries:
                        delay = self.retry_base_delay * (2**attempt)
                        logger.warning(
                            "Health check attempt timed out, retrying",
                            component_id=component.id,
                            attempt=attempt + 1,
                            delay_s=delay,
                        )
                        await asyncio.sleep(delay)
                except Exception as exc:
                    status = HealthStatus.UNHEALTHY
                    message = f"Check failed with error: {exc}"
                    if attempt < self.max_retries:
                        delay = self.retry_base_delay * (2**attempt)
                        logger.warning(
                            "Health check attempt error, retrying",
                            component_id=component.id,
                            attempt=attempt + 1,
                            delay_s=delay,
                            error=str(exc),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            "Health check error (final attempt)",
                            component_id=component.id,
                            error=str(exc),
                        )

            # Record circuit breaker result
            if self._circuit_breaker:
                if status == HealthStatus.HEALTHY:
                    self._circuit_breaker.record_success(component.endpoint)
                elif status == HealthStatus.UNHEALTHY:
                    self._circuit_breaker.record_failure(component.endpoint)

        latency_ms = (time.monotonic() - start) * 1000

        logger.info(
            "Health check complete",
            component_id=component.id,
            component_name=component.name,
            status=status.value,
            latency_ms=round(latency_ms, 2),
        )

        return ComponentHealth(
            id=component.id,
            name=component.name,
            type=component.type,
            status=status,
            endpoint=component.endpoint,
            latency_ms=round(latency_ms, 2),
            message=message,
            checked_at=datetime.now(UTC),
            dependencies=dependencies,
        )

    @abstractmethod
    async def _perform_check(self, component: ComponentInput) -> tuple[HealthStatus, str]:
        """Execute the actual health probe.

        Args:
            component: The component to probe.

        Returns:
            A tuple of (HealthStatus, human-readable message).

        Raises:
            Any exception — will be caught by ``check()`` and recorded
            as UNHEALTHY.
        """
        ...
