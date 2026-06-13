"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables (uppercase).
    For local development, create a .env file in the project root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HealthCheck API"
    app_version: str = "0.1.0"
    environment: Literal["dev", "staging", "prod"] = "dev"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # OpenTelemetry Tracing
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "healthcheck-api"

    # Prometheus Metrics
    metrics_enabled: bool = True

    # Health Check behaviour
    default_check_timeout_seconds: float = 5.0
    check_max_retries: int = 2
    check_retry_base_delay_seconds: float = 0.5
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_seconds: float = 30.0
    evaluation_timeout_seconds: float = 60.0
    propagation_mode: Literal["strict", "lenient", "none"] = "strict"
    max_components: int = 100

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 10

    # Simulation
    sim_hostname_suffix: str = ".sim"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
