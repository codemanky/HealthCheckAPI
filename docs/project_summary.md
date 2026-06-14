# HealthCheckAPI — Project Summary

## Assumptions

- **Simulated endpoints** (`.sim` suffix) are sufficient to demonstrate DAG-based health propagation without requiring live infrastructure. Real HTTP/TCP checks are supported but not the primary demo path.
- **BFS traversal** reflects a natural dependency evaluation order — leaf nodes (deepest dependencies) are checked first, status degradation propagates upward.
- **DAGs only** — cyclic dependencies are treated as invalid input; detected and rejected at validation time.
- Component health is **stateless per request** — no history, trending, or alerting is tracked between evaluations.

---

## Features Implemented

- **DAG-based health evaluation** — BFS traversal with async HTTP/TCP checks and dependency-aware status propagation (UNHEALTHY dep → parent becomes DEGRADED).
- **Resiliency patterns** — per-component timeouts, configurable retries, and a circuit breaker to prevent cascade failures in prolonged outages.
- **Simulated checks** — `.sim` hostname endpoints for deterministic testing without real services (healthy, unhealthy, degraded, flaky, slow, timeout).
- **DAG visualisation** — PNG rendered via `graphviz`, nodes colour-coded by health status, returned as binary or base64 JSON.
- **Observability** — structured JSON logging (`structlog`), Prometheus metrics (`/metrics`), OpenTelemetry tracing, and a request logging middleware.
- **Input validation** — strict Pydantic schemas reject duplicate IDs, self-loops, unknown edge references, and invalid URL schemes at request time.
- **CI/CD pipeline** — GitHub Actions CI (lint, typecheck, test, Docker build, Terraform validate) gating a CD pipeline that builds, pushes to Artifact Registry, deploys to Cloud Run, and smoke tests.

---

## Intentionally Excluded

- **Platform & network health checks** — omitted by design. If the app is reachable, the network path and underlying platform are implicitly healthy. Adding explicit checks would duplicate what Cloud Run's own health probes already cover.
- **Persistent state / history** — no database; each `/health/evaluate` call is fully self-contained. Out of scope for a stateless demo API.
- **Authentication on API endpoints** — Cloud Run itself is the auth boundary; internal API endpoints are open. Production hardening would add API key or IAM-based auth.
- **Multi-region deployment** — single `us-central1` region; no HA or failover configuration.

---

## Key Trade-offs & Design Decisions

- **GCP Cloud Run over Kubernetes** — chosen for familiarity and zero-ops scaling. Appropriate for a demo; Kubernetes would be needed for persistent workloads or multi-service orchestration.
- **Simulated checks as first-class citizens** — rather than mocking at the test layer, simulation is built into the routing logic. This made demos and CI tests fast and deterministic without needing a live environment.
- **`ruff` + `mypy` over a lighter lint setup** — strict linting caught real bugs (e.g. Pydantic `datetime` in `TYPE_CHECKING` block) but required significant CI iteration to configure correctly for the FastAPI `Depends` pattern.
- **Terraform for IaC despite small scope** — intentional over-engineering to demonstrate SRE practice; a `gcloud` script would have been simpler for a single service.
- **Workload Identity Federation over SA keys** — the right security choice (no long-lived secrets), but the most time-consuming part of the project due to IAM propagation complexity and `gcloud`'s credential-helper limitations inside GitHub Actions runners.

---

## AI Tool Usage

| Phase | Tool | Usage |
|---|---|---|
| Requirements & planning | Claude Opus 4.6 | Refined the problem statement, identified edge cases (cycle detection, propagation rules), and produced the initial implementation plan |
| Core implementation | Gemini Flash / Pro | Generated application code — DAG service, health checker, schemas, observability stack, Terraform modules, Dockerfiles |
| CI/CD debugging | Claude Sonnet 4.6 | Resolved complex multi-step failures in GitHub Actions (WIF IAM bindings, `ruff` version conflicts, Pydantic runtime import errors, Cloud Run auth) — Flash and Pro struggled to maintain context across the long chain of CI failures and repeatedly suggested conflicting fixes |
| Iteration & polish | All models | Incremental fixes to linting rules, test coverage gaps, and workflow path-ignore logic |

> **Observation:** Gemini Flash/Pro were effective for greenfield code generation but lost coherence when the problem required tracking 10+ prior failed states simultaneously (as in the WIF/Docker auth debugging). Claude Sonnet's longer effective context window was the deciding factor in finally resolving those issues.
