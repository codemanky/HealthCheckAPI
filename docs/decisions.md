# Design Decisions (ADRs)

## ADR-001: FastAPI as the Web Framework

**Context**: Need a Python web framework for building a REST API with async support and automatic OpenAPI documentation.

**Decision**: Use **FastAPI**.

**Consequences**:
- ✅ Native `async/await` support — required for concurrent health checks
- ✅ Automatic OpenAPI/Swagger UI at `/docs`
- ✅ Pydantic v2 integration for input validation
- ✅ Excellent performance (Starlette-based ASGI)
- ❌ Smaller ecosystem than Django REST Framework (acceptable for this use case)

---

## ADR-002: .sim Endpoint Pattern for Simulation

**Context**: Need to support simulated health checks without requiring real infrastructure, while keeping the ability to switch to real checks by simply changing configuration.

**Decision**: Components use `.sim` hostname suffix in their endpoint URLs to signal simulation. The URL path controls the simulated behaviour. The protocol (http, tcp) is preserved.

**Examples**:
```
http://api-gateway.sim/healthy       ← simulated, always healthy
tcp://db.sim:5432/unhealthy          ← simulated, always unhealthy
http://svc.sim/flaky?rate=0.3        ← simulated, 30% failure rate
http://real-api.internal/health      ← real HTTP check
tcp://prod-db:5432                   ← real TCP check
```

**Alternative considered**: A separate `check_type: simulate | real` field.

**Why .sim was chosen**:
- Moving to production requires only changing the hostname — no field changes
- The URL is self-describing: protocol, host, and behavior are all visible
- Natural analogy to `.local` and `.test` DNS conventions
- Simpler schema (one `endpoint` field vs two)

---

## ADR-003: BFS over DFS for Traversal

**Context**: Need to traverse the DAG and evaluate component health.

**Decision**: Use **Breadth-First Search (BFS)** with level grouping.

**Why BFS**:
- Nodes at the same BFS level have no dependency between them → can run **concurrently**
- `asyncio.gather()` on each level maximises throughput
- Level-order maps naturally to dependency layers (root first, leaves last)
- DFS would force sequential evaluation along each path

**Implementation**: `DAGService.bfs_levels()` returns `list[list[str]]`. Each inner list is one level evaluated with `asyncio.gather()`.

---

## ADR-004: Graphviz for DAG Visualization

**Context**: Need to render the DAG as a PNG image.

**Decision**: Use the **graphviz** Python library (wrapping the Graphviz `dot` CLI).

**Why Graphviz**:
- Purpose-built for directed graphs
- Excellent automatic layout algorithms (`dot` engine for hierarchical DAGs)
- Highly customisable node/edge styling
- Widely available (available as a system package on all platforms)
- Simple Python API via the `graphviz` package

**Alternative considered**: `networkx` + `matplotlib`. Rejected because matplotlib is heavier and produces less visually clean graph layouts for DAGs.

---

## ADR-005: No Persistent Storage

**Context**: The DAG is submitted per-request. The API evaluates it and returns results.

**Decision**: **No database, cache, or persistent storage**.

**Rationale**:
- The DAG structure is inherently ephemeral (evaluated on-demand)
- Adding Cloud SQL/Redis would increase operational complexity and cost
- Stateless design enables horizontal scaling on Cloud Run naturally
- Results can be cached client-side if needed

**Trade-off**: No history of past evaluations. If audit trails are needed, Cloud Logging captures all evaluation results in structured JSON.

---

## ADR-006: Color Scheme (No Blue Tones)

**Context**: DAG visualization must not use bluish tones per requirements.

**Decision**: Warm palette with high-contrast accessibility:

| Status | Color | Hex |
|--------|-------|-----|
| HEALTHY | Green | `#2ecc71` |
| DEGRADED | Amber | `#f39c12` |
| UNHEALTHY | Red | `#e74c3c` |
| UNKNOWN | Gray | `#95a5a6` |

Edges to unhealthy nodes: dashed red (`#e74c3c`). Background: white. All text: white on colored nodes.

---

## ADR-007: Kahn's Algorithm for Cycle Detection

**Context**: Need to validate the submitted graph is a DAG (no cycles).

**Decision**: Use **Kahn's topological sort algorithm**.

**Why Kahn's**:
- O(V + E) time complexity
- Naturally identifies cycle-participating nodes (those with remaining in-degree > 0)
- Simple to implement and explain
- Used in both Pydantic schema validation and the DAGService double-check

**Alternative**: DFS-based cycle detection (white-gray-black coloring). Kahn's was chosen for its clarity and the ability to identify all cycle nodes.

---

## ADR-008: GitHub OIDC for GCP Authentication

**Context**: CI/CD needs to authenticate to GCP to push images and deploy.

**Decision**: Use **GitHub OIDC + Workload Identity Federation** — no long-lived service account keys stored as secrets.

**Why**:
- Keys stored as GitHub Secrets can be leaked, rotated incorrectly, or forgotten
- OIDC tokens are short-lived and automatically rotated
- WIF is the GCP-recommended pattern for CI/CD authentication
- `google-github-actions/auth` provides turnkey integration

---

## ADR-009: Input Validation Strategy

**Context**: Need robust validation of user-submitted DAG JSON.

**Decision**: Validate at two layers:
1. **Pydantic `field_validator`** — individual field rules (ID format, name length, endpoint scheme)
2. **Pydantic `model_validator(mode='after')`** — cross-field rules (uniqueness, edge references, self-loops)
3. **DAGService** — cycle detection after schema validation (belt-and-suspenders)

**Error format**: Structured JSON with machine-readable `code`, human-readable `message`, and `details` dict for programmatic handling.

---

## ADR-010: SLO Strategy

**Context**: Need to define reliability goals for the service.

**Decision**: Target 99.9% availability, P99 < 2s latency, and < 0.1% 5xx error rate. Error budgets dictate feature velocity.

**Why**: Provides clear, measurable targets aligned with Terraform alerts (uptime check, latency, error rate) to balance reliability and velocity.

---

## ADR-011: Configurable Propagation Modes

**Context**: Different teams may have different preferences on how upstream failures affect downstream status.

**Decision**: Support `strict` (propagate UNHEALTHY as DEGRADED), `lenient` (annotate only), and `none` modes.

**Why**: Hardcoding the propagation logic is inflexible. Configurable modes allow consumers to tailor the behaviour to their operational needs.
