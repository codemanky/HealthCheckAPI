"""In-memory Circuit Breaker pattern for health checks."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any


class CircuitState(StrEnum):
    """States of a Circuit Breaker."""

    CLOSED = "closed"  # Operating normally, requests pass through
    OPEN = "open"  # Failing, requests are fast-failed
    HALF_OPEN = "half-open"  # Recovering, one request allowed to test


class CircuitBreaker:
    """An in-memory circuit breaker to prevent hammering failing endpoints.

    The circuit breaker tracks failures per endpoint. When failures exceed
    the threshold, the circuit trips (OPEN). After a recovery timeout, it
    transitions to HALF_OPEN, allowing a single probe to test if the endpoint
    has recovered. If successful, it resets (CLOSED). If it fails, it trips
    again (OPEN).
    """

    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds

        # Internal state keyed by endpoint
        # Dict maps endpoint -> {"state": CircuitState, "failures": int, "last_failure_time": float}
        self._state: dict[str, dict[str, Any]] = {}

    def _get_entry(self, endpoint: str) -> dict[str, Any]:
        if endpoint not in self._state:
            self._state[endpoint] = {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "last_failure_time": 0.0,
            }
        return self._state[endpoint]

    def allow_request(self, endpoint: str) -> bool:
        """Check if a request to the endpoint should be allowed.

        Returns:
            True if the request should proceed, False if it should fast-fail.
        """
        entry = self._get_entry(endpoint)
        state = entry["state"]

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            now = time.monotonic()
            if now - entry["last_failure_time"] >= self.recovery_seconds:
                # Time to test the endpoint again
                entry["state"] = CircuitState.HALF_OPEN
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            # We are already testing the endpoint; deny other concurrent requests
            return False

        return True

    def record_success(self, endpoint: str) -> None:
        """Record a successful request to the endpoint."""
        entry = self._get_entry(endpoint)
        entry["state"] = CircuitState.CLOSED
        entry["failures"] = 0

    def record_failure(self, endpoint: str) -> None:
        """Record a failed request to the endpoint."""
        entry = self._get_entry(endpoint)
        entry["failures"] += 1
        entry["last_failure_time"] = time.monotonic()

        if entry["state"] == CircuitState.HALF_OPEN or entry["failures"] >= self.failure_threshold:
            entry["state"] = CircuitState.OPEN


# Global singleton instance for the application
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker(failure_threshold: int = 3, recovery_seconds: float = 30.0) -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )
    return _circuit_breaker
