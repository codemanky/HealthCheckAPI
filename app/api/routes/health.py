"""Health check API routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_checker
from app.core.config import Settings, get_settings
from app.models.schemas import DAGInput, LivenessResponse, SystemHealthResponse
from app.services.health_checker import HealthCheckerService

router = APIRouter(tags=["Health"])

# Application start time for uptime calculation
_START_TIME = time.monotonic()


@router.get(
    "/health",
    response_model=LivenessResponse,
    summary="Liveness check",
    description=(
        "Returns the application's liveness status, version, and uptime. "
        "Always returns 200 if the application is running."
    ),
)
async def liveness(settings: Settings = Depends(get_settings)) -> LivenessResponse:
    """GET /health — API liveness check."""
    return LivenessResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
    )


@router.post(
    "/health/evaluate",
    response_model=SystemHealthResponse,
    summary="Evaluate DAG health",
    description=(
        "Accepts a JSON DAG describing system components and their dependency "
        "relationships. Validates the DAG, traverses it via BFS, asynchronously "
        "evaluates each component's health, and returns an aggregated report.\n\n"
        "Use `.sim` hostname suffix in endpoints to simulate component health "
        "without making real network connections:\n"
        "- `http://api.sim/healthy` → HEALTHY\n"
        "- `http://db.sim/unhealthy` → UNHEALTHY\n"
        "- `http://svc.sim/degraded` → DEGRADED\n"
        "- `http://svc.sim/flaky?rate=0.3` → 30% failure rate\n"
        "- `tcp://cache.sim:6379/slow?latency=2000` → 2s delay\n"
    ),
)
async def evaluate_dag(
    dag_input: DAGInput,
    checker: HealthCheckerService = Depends(get_health_checker),
) -> SystemHealthResponse:
    """POST /health/evaluate — evaluate all DAG components and return health report."""
    return await checker.evaluate(dag_input)
