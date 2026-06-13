# Tech Stack Rules — Health Check API

> A Python API for evaluating system component health via a DAG-based model,
> deployed on GCP with Terraform, Docker, and GitHub Actions.

---

## 🏗️ Project Overview

This is a System Health Check API that models infrastructure components as
nodes in a Directed Acyclic Graph (DAG). Health checks propagate through
the graph — a component's health depends on its own status AND the health
of its downstream dependencies. The system supports async health evaluation,
configurable check strategies, and GCP-native observability.

---

## 🐍 Python Application

### Framework & Runtime
- Use **FastAPI** as the web framework (async-native, OpenAPI auto-docs).
- Target **Python 3.12+**. Use modern Python features (type hints, `match` statements, `dataclasses`, `asyncio`).
- Use **uvicorn** as the ASGI server.
- Use **httpx** for async HTTP client calls (health check probes).
- Use **pydantic v2** for request/response models and settings management.

### Project Structure
Follow a **modular package layout**:
```
app/
├── main.py                  # FastAPI app factory, lifespan events
├── api/
│   ├── routes/              # API route handlers (health, components, dag)
│   └── dependencies.py      # FastAPI dependency injection
├── core/
│   ├── config.py            # Pydantic Settings (env-based config)
│   ├── logging.py           # Structured logging setup
│   └── exceptions.py        # Custom exception classes
├── models/
│   ├── schemas.py           # Pydantic request/response schemas
│   └── enums.py             # HealthStatus, ComponentType enums
├── services/
│   ├── health_checker.py    # Core health check orchestration
│   ├── dag.py               # DAG construction, traversal, cycle detection
│   └── checks/              # Individual check strategies per component type
│       ├── base.py          # Abstract base check
│       ├── http_check.py    # HTTP endpoint checks
│       ├── tcp_check.py     # TCP port checks
│       ├── database_check.py
│       ├── redis_check.py
│       ├── pubsub_check.py
│       └── gcp_check.py     # GCP-specific service checks
├── observability/
│   ├── metrics.py           # Prometheus metrics
│   ├── tracing.py           # OpenTelemetry tracing setup
│   └── middleware.py        # Request logging, metrics middleware
└── tests/
    ├── conftest.py          # Shared fixtures
    ├── unit/                # Unit tests (mocked dependencies)
    ├── integration/         # Integration tests (real connections)
    └── e2e/                 # End-to-end API tests
```

### Coding Standards
- Always use **type hints** for function signatures and return types.
- Use **`async def`** for all I/O-bound operations (health checks, HTTP calls, DB queries).
- Prefer **`asyncio.gather()`** with `return_exceptions=True` for concurrent health checks.
- Use **dependency injection** via FastAPI's `Depends()` — avoid global state.
- Use **enums** (`HealthStatus.HEALTHY`, `HealthStatus.DEGRADED`, `HealthStatus.UNHEALTHY`) instead of raw strings.
- Write **docstrings** (Google style) for all public classes and functions.
- Keep route handlers thin — delegate logic to service classes.
- Use **`structlog`** for structured JSON logging (not `print()` or stdlib `logging`).
- Handle all exceptions with custom exception handlers — never return raw tracebacks to clients.

### Dependencies & Environment
- Use **`pyproject.toml`** for project metadata and dependencies (PEP 621).
- Use **`uv`** as the package manager and virtual environment tool.
- Pin exact dependency versions in a lockfile.
- Separate **production** and **development** dependencies.
- Use **`.env`** files for local development config (never commit secrets).
- Load config via **Pydantic Settings** with environment variable overrides.

### Testing
- Use **`pytest`** with **`pytest-asyncio`** for async test support.
- Use **`httpx.AsyncClient`** with FastAPI's `TestClient` for API tests.
- Use **`pytest-cov`** for coverage reporting (target: ≥ 80%).
- Mock external dependencies (GCP services, databases) in unit tests.
- Use **fixtures** in `conftest.py` for shared test setup.
- Name test files `test_<module>.py`, test functions `test_<behavior>`.

---

## 🐳 Docker

### Dockerfile Standards
- Use **multi-stage builds**: `builder` stage for dependencies, `runtime` stage for the app.
- Base image: **`python:3.12-slim`** (not `alpine` — avoid musl compatibility issues).
- Run as a **non-root user** (`appuser`).
- Use **`uv`** for dependency installation inside the container.
- Copy only necessary files (use `.dockerignore` aggressively).
- Expose port **8080** (GCP Cloud Run convention).
- Set `PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1`.
- Include a **`HEALTHCHECK`** instruction using the app's own health endpoint.
- Keep the final image **< 200MB**.

### Docker Compose
- Provide a `docker-compose.yml` for local development with:
  - The API service
  - PostgreSQL (simulating Cloud SQL)
  - Redis (simulating Memorystore)
  - A mock GCP service (if needed)

---

## 🏔️ Terraform (Infrastructure as Code)

### General Standards
- Use **Terraform >= 1.5** with the **Google provider**.
- Target **GCP** as the sole cloud platform.
- Organize Terraform code in the `terraform/` directory.
- Use a **modular structure**:
  ```
  terraform/
  ├── main.tf              # Root module, provider config
  ├── variables.tf         # Input variables
  ├── outputs.tf           # Output values
  ├── terraform.tfvars     # Variable values (not committed for secrets)
  ├── backend.tf           # Remote state config (GCS bucket)
  └── modules/
      ├── cloud_run/       # Cloud Run service
      ├── cloud_sql/       # Cloud SQL instance
      ├── networking/      # VPC, subnets, Cloud NAT
      ├── iam/             # Service accounts, roles
      ├── monitoring/      # Alerting policies, dashboards
      └── artifact_registry/ # Container image registry
  ```
- Use **`terraform fmt`** and **`terraform validate`** in CI.
- Use **`tflint`** for linting.
- Tag all resources with `project`, `environment`, and `managed_by = "terraform"` labels.
- Use **variables** for all environment-specific values (never hardcode project IDs, regions, etc.).
- Store state in a **GCS backend** with state locking.
- Use **workspaces** or **variable files** to manage `dev` / `staging` / `prod` environments.

### GCP Resources to Provision
- **Cloud Run** — Application deployment
- **Cloud SQL (PostgreSQL)** — Persistent storage (if needed)
- **Memorystore (Redis)** — Caching layer (if needed)
- **Artifact Registry** — Docker image storage
- **VPC + Subnets** — Network isolation
- **Cloud NAT** — Egress for private resources
- **IAM Service Accounts** — Least-privilege access
- **Secret Manager** — Secrets storage
- **Cloud Monitoring** — Alerts and dashboards
- **Cloud Logging** — Log sinks and filters

---

## 🔄 CI/CD — GitHub Actions

### Workflow Standards
- Place workflows in **`.github/workflows/`**.
- Use **separate workflows** for:
  - `ci.yml` — Lint, test, build on every PR
  - `cd.yml` — Deploy on merge to `main`
  - `terraform.yml` — Plan on PR, apply on merge to `main`
- Pin all action versions to **full SHA** (not tags) for security.
- Use **GitHub OIDC** for keyless GCP authentication (Workload Identity Federation) — never store GCP service account keys as secrets.
- Use **job-level permissions** with least privilege.
- Cache **`uv`** dependencies and Docker layers for faster builds.

### CI Pipeline Steps
1. **Lint** — `ruff check` and `ruff format --check`
2. **Type Check** — `mypy` with strict mode
3. **Unit Tests** — `pytest tests/unit/ --cov`
4. **Integration Tests** — `pytest tests/integration/` (with Docker services)
5. **Build Docker Image** — Multi-stage build
6. **Security Scan** — `trivy` image scan
7. **Terraform Validate** — `terraform fmt -check` + `terraform validate` + `tflint`

### CD Pipeline Steps
1. **Build & Push** — Push image to Artifact Registry
2. **Terraform Plan** — Generate plan for review
3. **Terraform Apply** — Apply infrastructure changes
4. **Deploy** — Update Cloud Run service with new image
5. **Smoke Test** — Hit health endpoint post-deploy
6. **Notify** — Post deployment status

---

## 📊 Observability

### Structured Logging
- Use **`structlog`** configured for JSON output in production, human-readable in dev.
- Include standard fields: `timestamp`, `level`, `message`, `service`, `trace_id`, `span_id`.
- Log **health check results** with component name, status, latency, and error details.
- Ship logs to **Cloud Logging** (automatic in Cloud Run).
- **NEVER** log secrets, credentials, or PII.

### Metrics
- Expose **Prometheus-compatible** metrics at `/metrics`.
- Track:
  - `health_check_duration_seconds` (histogram, labels: `component`, `check_type`, `status`)
  - `health_check_status` (gauge, labels: `component`, value: 0=unhealthy, 0.5=degraded, 1=healthy)
  - `http_request_duration_seconds` (histogram, labels: `method`, `path`, `status_code`)
  - `http_requests_total` (counter, labels: `method`, `path`, `status_code`)
  - `dag_evaluation_duration_seconds` (histogram)
- Use **`prometheus_client`** Python library.

### Distributed Tracing
- Use **OpenTelemetry** SDK for Python.
- Export traces to **Cloud Trace** (via OTLP exporter or GCP exporter).
- Instrument:
  - All incoming HTTP requests (FastAPI middleware)
  - All outgoing HTTP calls (httpx)
  - All database queries
  - DAG traversal spans (one span per component check)
- Propagate **trace context** across health check calls.

### Health Check Endpoint Design
- `GET /health` — Aggregate system health (the DAG result)
- `GET /health/components` — List all components and their individual status
- `GET /health/components/{id}` — Single component health detail
- `GET /health/dag` — Full DAG structure with health propagation
- Return **HTTP 200** for HEALTHY/DEGRADED, **HTTP 503** for UNHEALTHY.
- Include **response time**, **timestamp**, and **version** in all health responses.

---

## 📝 Documentation

### Required Documents
- **`README.md`** — Project overview, quickstart, architecture diagram
- **`docs/architecture.md`** — System design, DAG model, component taxonomy
- **`docs/api.md`** — API reference (supplement auto-generated OpenAPI docs)
- **`docs/decisions.md`** — Architecture Decision Records (ADRs) for key tradeoffs
- **`docs/observability.md`** — Logging, metrics, tracing strategy
- **`docs/deployment.md`** — How to deploy via CI/CD and manually
- **`CONTRIBUTING.md`** — Development setup, testing, and PR guidelines

### Documentation Style
- Use **Mermaid diagrams** for architecture and flow visualizations.
- Write ADRs in the format: Context → Decision → Consequences.
- Keep docs next to code — don't let them drift.

---

## 🔒 Security

- Never commit secrets, API keys, or credentials. Use `.gitignore` and Secret Manager.
- Use **least-privilege IAM** — each service gets only the permissions it needs.
- Run containers as **non-root**.
- Scan dependencies with **`pip-audit`** or **`safety`**.
- Scan Docker images with **`trivy`**.
- Use **HTTPS everywhere** (enforced by Cloud Run).
- Validate all inputs with **Pydantic** models.

---

## 🎨 Code Formatting & Linting

- Use **`ruff`** for both linting and formatting (replaces flake8, isort, black).
- Use **`mypy`** in strict mode for type checking.
- Use **`pre-commit`** hooks for local enforcement.
- Line length: **88 characters** (ruff default).
- Import sorting: **isort-compatible** (via ruff).

---

## 📦 Version Control

- Use **conventional commits**: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`.
- Branch naming: `feature/<name>`, `fix/<name>`, `docs/<name>`.
- Always squash-merge PRs.
- Maintain a **`CHANGELOG.md`** (or auto-generate from conventional commits).
