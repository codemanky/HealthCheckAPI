"""FastAPI application factory with lifespan, middleware, and router registration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.rate_limiter import RateLimitingMiddleware
from app.api.routes import dag, health
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.observability.metrics import make_metrics_app
from app.observability.middleware import RequestLoggingMiddleware
from app.observability.tracing import configure_tracing

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    settings = get_settings()

    # Configure observability
    configure_logging(settings)
    configure_tracing(settings)

    logger.info(
        "Health Check API starting",
        version=__version__,
        environment=settings.environment,
        log_format=settings.log_format,
        otel_enabled=settings.otel_enabled,
        metrics_enabled=settings.metrics_enabled,
    )

    yield

    logger.info("Health Check API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Health Check API",
        description=(
            "A Python API for evaluating the health of system components "
            "arranged as a Directed Acyclic Graph (DAG).\n\n"
            "Submit a JSON DAG, get async health checks, a tabular summary, "
            "and a PNG visualisation with unhealthy components highlighted in red."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception handlers ---
    register_exception_handlers(app)

    # --- Routers ---
    app.include_router(health.router)
    app.include_router(dag.router)

    # --- Prometheus /metrics endpoint ---
    if settings.metrics_enabled:
        metrics_app = make_metrics_app()
        app.mount("/metrics", metrics_app)  # type: ignore

    return app


# Singleton instance used by uvicorn
app = create_app()
