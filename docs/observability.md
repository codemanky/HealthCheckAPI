# Observability Guide

## Overview

The Health Check API is instrumented with three observability pillars:
1. **Structured Logging** — via `structlog` → Cloud Logging
2. **Metrics** — via `prometheus-client` → Cloud Monitoring
3. **Distributed Tracing** — via OpenTelemetry → GCP Cloud Trace

---

## Logging

### Strategy

Logs are emitted as **structured JSON** to stdout in production. Cloud Run automatically ingests stdout into Cloud Logging with full structured field indexing.

In development, logs use a colourised console renderer for readability.

### Log Format

```json
{
  "timestamp": "2026-06-12T04:00:00Z",
  "level": "info",
  "logger": "app.services.health_checker",
  "event": "Health check complete",
  "component_id": "step-4",
  "component_name": "Inventory Database",
  "status": "unhealthy",
  "latency_ms": 51.22,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

### Configuration

| Env Var | Values | Default |
|---------|--------|---------|
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `LOG_FORMAT` | `json` (production), `console` (development) | `console` |

### Key Log Events

| Event | Level | Description |
|-------|-------|-------------|
| `DAG built` | INFO | Graph construction completed |
| `BFS traversal complete` | DEBUG | Level counts and sizes |
| `Health check complete` | INFO | Per-component result with latency |
| `Health propagated from dependency` | INFO | Propagation applied |
| `Health check summary` | INFO | Full ASCII table of results |
| `HTTP request` | INFO | Method, path, status, duration for every request |

---

## Metrics

The `/metrics` endpoint exposes Prometheus-format metrics. These are scraped by Cloud Monitoring via its Prometheus integration.

### Metric Catalog

#### Health Check Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `health_check_duration_seconds` | Histogram | `component_id`, `component_type`, `status` | Individual check duration |
| `health_check_status` | Gauge | `component_id`, `component_name`, `component_type` | Current component health (1=healthy, 0.5=degraded, 0=unhealthy) |
| `dag_evaluation_duration_seconds` | Histogram | — | Total DAG evaluation time |

#### HTTP Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_request_duration_seconds` | Histogram | `method`, `path`, `status_code` | Request latency |
| `http_requests_total` | Counter | `method`, `path`, `status_code` | Request count |

### Example Queries (PromQL)

```promql
# P99 latency for evaluate endpoint
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{path="/health/evaluate"}[5m]))

# Error rate (5xx)
rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m])

# Components currently unhealthy
health_check_status == 0

# Avg DAG evaluation time
rate(dag_evaluation_duration_seconds_sum[5m]) / rate(dag_evaluation_duration_seconds_count[5m])
```

---

## Distributed Tracing

### Setup

OpenTelemetry is configured via `app/observability/tracing.py`:
- **Production** (`OTEL_ENABLED=true`): Exports spans to **GCP Cloud Trace** via `CloudTraceSpanExporter`
- **Development**: Console exporter (traces printed to stdout)

FastAPI is automatically instrumented via `FastAPIInstrumentor`.

### Configuration

| Env Var | Description | Default |
|---------|-------------|---------|
| `OTEL_ENABLED` | Enable tracing | `false` |
| `OTEL_ENDPOINT` | OTLP gRPC endpoint | `http://localhost:4317` |
| `OTEL_SERVICE_NAME` | Service name in traces | `healthcheck-api` |

### Trace Context in Logs

When a trace is active, `trace_id` and `span_id` are automatically injected into every log record, enabling trace-to-log correlation in Cloud Console.

---

## Alerting

Two alert policies are provisioned via Terraform (`terraform/modules/monitoring/main.tf`):

| Alert | Threshold | Duration |
|-------|-----------|----------|
| High 5xx error rate | > 5% of requests | 5 minutes |
| P99 latency | > 2 seconds | 5 minutes |

An uptime check verifies the `/health` endpoint is reachable every 60 seconds.

To add notification channels (email, PagerDuty, Slack):
1. Create a `google_monitoring_notification_channel` resource in Terraform
2. Reference its ID in the `notification_channels` list of alert policies

---

## Health Checks

### Application Health (`GET /health`)

Returns application liveness with uptime and version:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "prod",
  "uptime_seconds": 3600.5
}
```

This endpoint is used as the Cloud Run **startup probe** and **liveness probe**.

### Container Health

The Docker image includes a `HEALTHCHECK` instruction:
```
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```
