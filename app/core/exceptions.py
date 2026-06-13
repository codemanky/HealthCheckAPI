"""Custom exceptions and FastAPI exception handlers."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse



class DAGValidationError(Exception):
    """Raised when the DAG structure is invalid (cycle, missing nodes, etc.).

    Args:
        code: Machine-readable error code (e.g. CYCLE_DETECTED).
        message: Human-readable description.
        details: Optional dict of extra context for the client.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class HealthCheckTimeoutError(Exception):
    """Raised when an individual component health check exceeds its timeout.

    Args:
        component_id: ID of the component that timed out.
        timeout_seconds: The timeout threshold that was exceeded.
    """

    def __init__(self, component_id: str, timeout_seconds: float) -> None:
        self.component_id = component_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Health check for component '{component_id}' timed out "
            f"after {timeout_seconds}s"
        )


def _error_response(
    code: str,
    message: str,
    details: dict | None = None,
    status_code: int = 422,
) -> JSONResponse:
    """Build a consistent error response body."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(DAGValidationError)
    async def dag_validation_error_handler(
        request: Request, exc: DAGValidationError
    ) -> JSONResponse:
        return _error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=422,
        )

    @app.exception_handler(HealthCheckTimeoutError)
    async def health_check_timeout_handler(
        request: Request, exc: HealthCheckTimeoutError
    ) -> JSONResponse:
        return _error_response(
            code="HEALTH_CHECK_TIMEOUT",
            message=str(exc),
            details={
                "component_id": exc.component_id,
                "timeout_seconds": exc.timeout_seconds,
            },
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return _error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
