"""Tests for RateLimiter."""

from __future__ import annotations

from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limiter import RateLimiter, RateLimitingMiddleware


def test_rate_limiter_logic() -> None:
    limiter = RateLimiter(requests_per_minute=2)
    ip = "127.0.0.1"

    with mock.patch("time.monotonic", return_value=100.0):
        allowed, retry = limiter.is_allowed(ip)
        assert allowed is True

        allowed, retry = limiter.is_allowed(ip)
        assert allowed is True

        allowed, retry = limiter.is_allowed(ip)
        assert allowed is False
        assert retry == 60.0

    # Simulate waiting 61 seconds
    with mock.patch("time.monotonic", return_value=161.0):
        allowed, retry = limiter.is_allowed(ip)
        assert allowed is True


def test_rate_limiting_middleware() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitingMiddleware)

    @app.get("/health/evaluate")
    async def evaluate() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/other")
    async def other() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    # Need to mock the global settings so rate limit is enabled
    with (
        mock.patch("app.api.rate_limiter.get_settings") as mock_settings,
        mock.patch("app.api.rate_limiter.get_rate_limiter") as mock_get_limiter,
    ):
        mock_settings.return_value.rate_limit_enabled = True
        mock_settings.return_value.rate_limit_rpm = 1

        mock_limiter = mock.Mock()
        mock_get_limiter.return_value = mock_limiter

        # Other paths should pass regardless
        mock_limiter.is_allowed.return_value = (False, 30.0)
        res = client.get("/other")
        assert res.status_code == 200

        # Evaluate should be blocked
        res = client.get("/health/evaluate")
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert res.headers["Retry-After"] == "31"
        assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
