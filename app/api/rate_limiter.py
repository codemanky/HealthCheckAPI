"""Simple in-memory token bucket rate limiter middleware."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import get_settings


class RateLimiter:
    """In-memory rate limiter using a sliding window or token bucket.

    For simplicity, we use a basic windowed approach here tracking requests
    per minute per client IP.
    """

    def __init__(self, requests_per_minute: int) -> None:
        self.rpm = requests_per_minute
        # Maps IP to list of request timestamps
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> tuple[bool, float]:
        """Check if a request from this IP is allowed.

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.monotonic()
        cutoff = now - 60.0

        # Initialize or clean up old requests
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        
        # Keep only requests within the last minute
        self._requests[client_ip] = [ts for ts in self._requests[client_ip] if ts > cutoff]

        if len(self._requests[client_ip]) >= self.rpm:
            # Denied. Retry after the oldest request in the window falls out.
            oldest = self._requests[client_ip][0]
            retry_after = 60.0 - (now - oldest)
            return False, retry_after

        # Allowed
        self._requests[client_ip].append(now)
        return True, 0.0


# Global singleton
_rate_limiter: RateLimiter | None = None

def get_rate_limiter(rpm: int) -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(rpm)
    return _rate_limiter


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on specific paths."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Any:
        settings = get_settings()

        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Only rate limit expensive endpoints
        if request.url.path not in ("/health/evaluate", "/dag/visualize"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limiter = get_rate_limiter(settings.rate_limit_rpm)

        allowed, retry_after = limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "details": {"retry_after_seconds": round(retry_after, 1)}
                    }
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        return await call_next(request)
