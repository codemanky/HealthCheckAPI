"""Prometheus metrics definitions and ASGI app for /metrics endpoint."""

from __future__ import annotations

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)

# --- Health check metrics ---

HEALTH_CHECK_DURATION = Histogram(
    "health_check_duration_seconds",
    "Duration of individual component health checks",
    labelnames=["component_id", "component_type", "status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HEALTH_CHECK_STATUS = Gauge(
    "health_check_status",
    "Current health status of a component (1=healthy, 0.5=degraded, 0=unhealthy)",
    labelnames=["component_id", "component_name", "component_type"],
)

DAG_EVALUATION_DURATION = Histogram(
    "dag_evaluation_duration_seconds",
    "Total duration of a full DAG health evaluation",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

CIRCUIT_BREAKER_OPEN_TOTAL = Counter(
    "circuit_breaker_open_total",
    "Total number of times a circuit breaker prevented a request",
    labelnames=["component_id", "endpoint"],
)

# --- HTTP request metrics ---

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests to this API",
    labelnames=["method", "path", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests to this API",
    labelnames=["method", "path", "status_code"],
)

# Numeric mapping for HEALTH_CHECK_STATUS gauge
STATUS_GAUGE_VALUES = {
    "healthy": 1.0,
    "degraded": 0.5,
    "unhealthy": 0.0,
    "unknown": -1.0,
}


def record_component_health(
    component_id: str,
    component_name: str,
    component_type: str,
    status: str,
    latency_seconds: float,
) -> None:
    """Record health check metrics for a single component.

    Args:
        component_id: Component identifier.
        component_name: Human-readable name.
        component_type: ComponentType value string.
        status: HealthStatus value string.
        latency_seconds: Check latency in seconds.
    """
    HEALTH_CHECK_DURATION.labels(
        component_id=component_id,
        component_type=component_type,
        status=status,
    ).observe(latency_seconds)

    HEALTH_CHECK_STATUS.labels(
        component_id=component_id,
        component_name=component_name,
        component_type=component_type,
    ).set(STATUS_GAUGE_VALUES.get(status, -1.0))


def make_metrics_app() -> object:
    """Create the ASGI app to serve /metrics."""
    return make_asgi_app()
