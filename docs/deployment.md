# Deployment Guide

## Local Development

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Graphviz system package

### Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install graphviz (macOS)
brew install graphviz
# or Ubuntu/Debian
# sudo apt-get install -y graphviz

# Clone and enter the repository
cd HealthCheckAPI

# Create virtual environment and install dependencies
uv venv && uv pip install -e ".[dev]"
source .venv/bin/activate
```

### Run the API

```bash
uvicorn app.main:app --reload --port 8080
```

Open [http://localhost:8080/docs](http://localhost:8080/docs) for the interactive Swagger UI.

### Run Tests

```bash
# All tests with coverage
pytest tests/ --cov=app --cov-report=term-missing -v

# Unit tests only
pytest tests/unit/ -v

# E2E tests only
pytest tests/e2e/ -v
```

---

## Docker

### Build

```bash
docker build -t healthcheck-api:local .
```

### Run

```bash
docker run -p 8080:8080 \
  -e ENVIRONMENT=dev \
  -e LOG_FORMAT=console \
  healthcheck-api:local
```

### Docker Compose

```bash
docker-compose up
```

### Verify

```bash
curl http://localhost:8080/health
# {"status":"ok","version":"0.1.0","environment":"dev","uptime_seconds":5.12}

curl -X POST http://localhost:8080/health/evaluate \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_dag.json | python3 -m json.tool
```

---

## GCP Cloud Run (Production)

### Prerequisites

1. A GCP project with billing enabled
2. `gcloud` CLI installed and authenticated
3. Terraform >= 1.5 installed
4. A GCS bucket for Terraform state

### One-time Setup

#### 1. Create Terraform state bucket

```bash
gcloud storage buckets create gs://your-tf-state-bucket \
  --location=us-central1 \
  --uniform-bucket-level-access
```

#### 2. Update backend config

Edit `terraform/backend.tf`:
```hcl
bucket = "your-tf-state-bucket"
```

#### 3. Configure tfvars

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit with your project_id, region, etc.
```

#### 4. Apply Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This provisions:
- Artifact Registry Docker repository
- Cloud Run service with startup/liveness probes
- IAM service account with least-privilege roles
- Cloud Monitoring uptime check and alert policies

#### 5. Configure GitHub Actions

Add these to your GitHub repository:

**Secrets**:
- `WIF_PROVIDER` — Workload Identity Federation provider resource name
- `WIF_SERVICE_ACCOUNT` — Service account email for GitHub Actions

**Variables**:
- `GCP_PROJECT_ID` — Your GCP project ID
- `GCP_REGION` — Deployment region (e.g., `us-central1`)

### Continuous Deployment

Push to `main` branch to trigger automatic deployment:

```
CI checks → Build & push Docker image → Deploy to Cloud Run → Smoke test
```

The CD pipeline uses **GitHub OIDC + Workload Identity Federation** — no service account keys stored.

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment name | `dev` |
| `LOG_LEVEL` | Log level | `INFO` |
| `LOG_FORMAT` | `json` or `console` | `console` |
| `METRICS_ENABLED` | Enable `/metrics` endpoint | `true` |
| `OTEL_ENABLED` | Enable Cloud Trace | `false` |
| `OTEL_SERVICE_NAME` | Service name in traces | `healthcheck-api` |
| `DEFAULT_CHECK_TIMEOUT_SECONDS` | Per-component check timeout | `5.0` |
| `MAX_COMPONENTS` | Max DAG nodes allowed | `100` |
