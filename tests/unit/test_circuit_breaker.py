"""Tests for CircuitBreaker."""

from __future__ import annotations

from unittest import mock

from app.services.checks.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_initial_state() -> None:
    cb = CircuitBreaker()
    assert cb.allow_request("http://test") is True


def test_circuit_breaker_trips_after_failures() -> None:
    cb = CircuitBreaker(failure_threshold=3)
    endpoint = "http://test"

    cb.record_failure(endpoint)
    cb.record_failure(endpoint)
    assert cb.allow_request(endpoint) is True
    assert cb._get_entry(endpoint)["state"] == CircuitState.CLOSED

    cb.record_failure(endpoint)
    assert cb.allow_request(endpoint) is False
    assert cb._get_entry(endpoint)["state"] == CircuitState.OPEN


def test_circuit_breaker_recovers_after_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=0.1)
    endpoint = "http://test"

    cb.record_failure(endpoint)
    cb.record_failure(endpoint)
    assert cb.allow_request(endpoint) is False

    # Mock time to simulate recovery
    with mock.patch("time.monotonic", return_value=cb._get_entry(endpoint)["last_failure_time"] + 0.2):
        assert cb.allow_request(endpoint) is True
        assert cb._get_entry(endpoint)["state"] == CircuitState.HALF_OPEN

        # Second request while HALF_OPEN should be denied
        assert cb.allow_request(endpoint) is False


def test_circuit_breaker_closes_on_success() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_seconds=0.1)
    endpoint = "http://test"

    cb.record_failure(endpoint)

    with mock.patch("time.monotonic", return_value=cb._get_entry(endpoint)["last_failure_time"] + 0.2):
        assert cb.allow_request(endpoint) is True
        cb.record_success(endpoint)
        assert cb._get_entry(endpoint)["state"] == CircuitState.CLOSED
        assert cb.allow_request(endpoint) is True
