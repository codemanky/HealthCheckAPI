# Service Level Objectives (SLOs)

This document defines the Service Level Objectives (SLOs) for the HealthCheck API, translating our reliability goals into measurable targets.

## SLO Targets

| Objective | Target | SLI (Service Level Indicator) | Error Budget (30 days) |
|-----------|--------|--------------------------------|------------------------|
| **Availability** | 99.9% | Percentage of successful requests (HTTP 2xx) to the `/health` liveness endpoint. | ~43 minutes of downtime |
| **Latency** | 99th percentile < 2s | Response time for `/health/evaluate` measured at the load balancer / gateway. | 1% of requests > 2s |
| **Error Rate** | < 0.1% | Percentage of HTTP 5xx responses out of total requests to `/health/evaluate`. | 1 in 1000 requests |

## Error Budgets & Burn Rates

We use error budgets to balance reliability with feature velocity. If an error budget is depleted:
- New feature deployments may be frozen.
- Engineering focus shifts to reliability improvements.

### Alerting Strategy

Our alerting (configured via Terraform in `terraform/modules/monitoring`) is aligned with these SLOs:
1. **Availability Alert**: Triggers if the `/health` endpoint fails the uptime check.
2. **Latency Alert**: Triggers if the P99 latency of `/health/evaluate` exceeds 2 seconds for a sustained period.
3. **Error Rate Alert**: Triggers if the 5xx error rate exceeds 5% over a short window (burn rate alert).

## Dependencies

Meeting these SLOs requires that the dependencies we evaluate (the components in the DAG) adhere to their own timeouts. The HealthCheck API protects its own availability using:
- Strict timeouts on all downstream health checks.
- Circuit breakers to fast-fail when downstream services are degraded.
- Rate limiting to prevent evaluation abuse.
