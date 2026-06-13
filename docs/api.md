# API Reference

## Base URL

- **Local**: `http://localhost:8080`
- **Production**: `https://<cloud-run-url>` (from `terraform output cloud_run_url`)

---

## GET /health

**Liveness check.** Returns 200 if the application is running.

### Response

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "dev",
  "uptime_seconds": 3600.12
}
```

```bash
curl http://localhost:8080/health
```

---

## POST /health/evaluate

**Evaluate DAG health.** Accepts a DAG JSON, performs health checks on all components, and returns an aggregated report.

### Request Body

```json
{
  "components": [
    {
      "id": "step-1",
      "name": "API Gateway",
      "type": "gateway",
      "endpoint": "http://api-gateway.sim/healthy",
      "metadata": {}
    }
  ],
  "edges": [
    ["step-1", "step-2"]
  ]
}
```

#### Component Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Unique ID (`[a-zA-Z0-9_-]`, max 64 chars) |
| `name` | string | ✓ | Display name (1–128 chars) |
| `type` | enum | ✓ | `service`, `database`, `cache`, `queue`, `gateway`, `external`, `custom` |
| `endpoint` | string | ✓ | URL with scheme `http`, `https`, or `tcp` |
| `metadata` | object | — | Free-form key/value pairs |

#### Simulated Endpoints

| Endpoint Pattern | Behavior |
|------------------|----------|
| `http://*.sim/healthy` | Always HEALTHY (50–200ms) |
| `http://*.sim/unhealthy` | Always UNHEALTHY (50–200ms) |
| `http://*.sim/degraded` | Always DEGRADED (200–500ms) |
| `http://*.sim/flaky?rate=0.3` | UNHEALTHY 30% of the time |
| `tcp://*.sim:PORT/slow?latency=2000` | HEALTHY after 2000ms delay |
| `http://*.sim/timeout` | Times out |

### Response

```json
{
  "overall_status": "unhealthy",
  "total_components": 11,
  "healthy_count": 7,
  "degraded_count": 2,
  "unhealthy_count": 2,
  "evaluation_time_ms": 1507.22,
  "evaluated_at": "2026-06-12T04:00:00Z",
  "version": "0.1.0",
  "components": [
    {
      "id": "step-1",
      "name": "API Gateway",
      "type": "gateway",
      "status": "healthy",
      "endpoint": "http://api-gateway.sim/healthy",
      "latency_ms": 113.1,
      "message": "Simulated: component is healthy",
      "checked_at": "2026-06-12T04:00:00Z",
      "dependencies": ["step-2"]
    }
  ]
}
```

Overall status is the **worst** status among all components (`unhealthy` > `degraded` > `unknown` > `healthy`).

### cURL Example

```bash
curl -X POST http://localhost:8080/health/evaluate \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_dag.json | python3 -m json.tool
```

---

## POST /dag/visualize

**Render DAG as PNG.** Optionally runs health evaluation to colour nodes by status.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `evaluate` | boolean | `true` | Run health evaluation before rendering |
| `format` | string | `png` | `png` (binary) or `base64` (JSON) |

### Response (PNG)

Returns `image/png` binary. Nodes are coloured:
- 🟢 **Green** (`#2ecc71`): HEALTHY
- 🟡 **Amber** (`#f39c12`): DEGRADED
- 🔴 **Red** (`#e74c3c`): UNHEALTHY
- ⬜ **Gray** (`#95a5a6`): UNKNOWN

Edges to unhealthy nodes are dashed red.

### Response (base64)

```json
{
  "image_base64": "<base64-encoded-png>",
  "format": "png",
  "component_count": 11,
  "edge_count": 11
}
```

### cURL Examples

```bash
# Save PNG to file
curl -X POST http://localhost:8080/dag/visualize \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_dag.json \
  --output dag.png

# Get base64 JSON
curl -X POST "http://localhost:8080/dag/visualize?format=base64" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_dag.json | python3 -m json.tool
```

---

## GET /metrics

**Prometheus metrics.** Returns metrics in Prometheus text format for scraping.

```bash
curl http://localhost:8080/metrics
```

---

## Validation Error Catalog

All validation errors return HTTP **422** with this structure:

```json
{
  "error": {
    "code": "DUPLICATE_COMPONENT_ID",
    "message": "Duplicate component IDs found: ['step-1']. Each component must have a unique ID.",
    "details": {}
  }
}
```

### Error Codes

| Code | Trigger | Example |
|------|---------|---------|
| `EMPTY_COMPONENTS` | `components` list is empty | `{"components": [], "edges": []}` |
| `TOO_MANY_COMPONENTS` | > 100 components | 101 components in the list |
| `DUPLICATE_COMPONENT_ID` | Same `id` used twice | Two components with `id: "svc-1"` |
| `INVALID_COMPONENT_ID` | ID contains invalid chars | `id: "step 1!"` |
| `COMPONENT_ID_TOO_LONG` | ID > 64 chars | 65-character ID |
| `INVALID_COMPONENT_NAME` | Empty or > 128 char name | `name: ""` |
| `INVALID_ENDPOINT` | Unsupported URL scheme | `endpoint: "ftp://bad.host"` |
| `INVALID_COMPONENT_TYPE` | Unknown type value | `type: "magic"` |
| `EDGE_REFERENCES_UNKNOWN_COMPONENT` | Edge references non-existent ID | `["svc-1", "nonexistent"]` |
| `SELF_REFERENCING_EDGE` | Edge where both IDs are the same | `["svc-1", "svc-1"]` |
| `DUPLICATE_EDGE` | Same edge appears twice | `["a","b"], ["a","b"]` |
| `CYCLE_DETECTED` | DAG contains a cycle | `a→b→c→a` |
| `INVALID_SIM_BEHAVIOR` | Invalid `.sim` endpoint path | `http://svc.sim/banana` |

---

## OpenAPI / Swagger UI

Full interactive API documentation is available at:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI JSON: `http://localhost:8080/openapi.json`
