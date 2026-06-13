"""OpenTelemetry tracing configuration."""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_tracing(settings: Settings) -> None:
    """Set up OpenTelemetry tracing with the appropriate exporter.

    - In production (otel_enabled=True): exports to GCP Cloud Trace via OTLP.
    - In development: exports to console (no-op if neither is configured).

    Args:
        settings: Application settings.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("OpenTelemetry SDK not installed — tracing disabled")
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otel_enabled:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            exporter = CloudTraceSpanExporter()  # type: ignore[no-untyped-call]
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("GCP Cloud Trace exporter configured")
        except Exception as exc:
            logger.warning(
                "Failed to configure GCP Cloud Trace exporter — falling back to console",
                error=str(exc),
            )
            _add_console_exporter(provider)
    else:
        if settings.environment == "dev":
            _add_console_exporter(provider)

    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except Exception as exc:
        logger.warning("FastAPI OTel instrumentation failed", error=str(exc))


def _add_console_exporter(provider: object) -> None:
    """Add a console span exporter for local development visibility."""
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        # Use a simple stdout exporter if available
        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            cast_provider: TracerProvider = provider  # type: ignore[assignment]
            cast_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        except ImportError:
            pass
    except ImportError:
        pass
