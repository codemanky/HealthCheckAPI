# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files and source code
COPY pyproject.toml README.md ./
COPY app/ ./app/

# Install production dependencies into a virtual environment
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache-dir ".[dev]" || \
    uv pip install --python /opt/venv/bin/python --no-cache-dir .

# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# Install graphviz system package (required for DAG rendering)
RUN apt-get update && \
    apt-get install -y --no-install-recommends graphviz curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY app/ ./app/

# Set environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Switch to non-root user
USER appuser

EXPOSE 8080

# Health check using the app's own liveness endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
