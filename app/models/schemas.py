"""Pydantic request/response schemas with comprehensive input validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, model_validator

from app.models.enums import ComponentType, HealthStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_COMPONENT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_VALID_SCHEMES = {"http", "https", "tcp"}
_SIM_SUFFIX = ".sim"
_VALID_SIM_PATHS = {"/healthy", "/unhealthy", "/degraded", "/flaky", "/slow", "/timeout"}

MAX_COMPONENT_ID_LENGTH = 64
MAX_COMPONENT_NAME_LENGTH = 128
MAX_COMPONENTS = 100


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ComponentInput(BaseModel):
    """A single system component node in the DAG.

    Args:
        id: Unique alphanumeric identifier for the component (hyphens/underscores allowed).
        name: Human-readable display name (1–128 chars).
        type: Logical category of the component.
        endpoint: URL describing how to health-check this component.
                  Use real URLs for live checks (e.g. ``http://svc.internal/health``).
                  Use ``.sim`` hostname suffix for simulation
                  (e.g. ``http://api.sim/healthy``, ``tcp://db.sim:5432/unhealthy``).
        metadata: Optional free-form key/value pairs attached to the component.
    """

    id: str
    name: str
    type: ComponentType = ComponentType.SERVICE
    endpoint: str
    metadata: dict[str, Any] = {}

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is non-empty, ≤64 chars, and alphanumeric+hyphens+underscores."""
        if not v:
            raise ValueError("Component ID must not be empty")
        if len(v) > MAX_COMPONENT_ID_LENGTH:
            raise ValueError(f"Component ID '{v}' exceeds maximum length of {MAX_COMPONENT_ID_LENGTH} characters")
        if not _VALID_COMPONENT_ID_RE.match(v):
            raise ValueError(
                f"Component ID '{v}' contains invalid characters. "
                "Only letters, digits, hyphens (-) and underscores (_) are allowed."
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is 1–128 chars."""
        v = v.strip()
        if not v:
            raise ValueError("Component name must not be empty")
        if len(v) > MAX_COMPONENT_NAME_LENGTH:
            raise ValueError(f"Component name exceeds maximum length of {MAX_COMPONENT_NAME_LENGTH} characters")
        return v

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint URL scheme and simulated endpoint path."""
        try:
            parsed = urlparse(v)
        except Exception:
            raise ValueError(f"Invalid endpoint URL: '{v}'")

        if parsed.scheme not in _VALID_SCHEMES:
            raise ValueError(
                f"Invalid endpoint scheme '{parsed.scheme}'. Allowed schemes: {', '.join(sorted(_VALID_SCHEMES))}"
            )

        hostname = parsed.hostname or ""
        if hostname.endswith(_SIM_SUFFIX):
            # Validate simulated path
            path = parsed.path.rstrip("/") or "/"
            # Allow path with or without query string base
            base_path = path.split("?")[0]
            if base_path not in _VALID_SIM_PATHS:
                raise ValueError(
                    f"Invalid simulation path '{parsed.path}' in endpoint '{v}'. "
                    f"Valid paths for .sim endpoints: "
                    f"{', '.join(sorted(_VALID_SIM_PATHS))}"
                )

        return v

    @property
    def is_simulated(self) -> bool:
        """Return True if this component uses a simulated (.sim) endpoint."""
        parsed = urlparse(self.endpoint)
        return (parsed.hostname or "").endswith(_SIM_SUFFIX)


class DAGInput(BaseModel):
    """Input describing a system of components and their dependency relationships.

    The ``edges`` list defines directed edges where ``(from_id, to_id)`` means
    the component ``from_id`` depends on ``to_id``.  The resulting graph must
    be a valid Directed Acyclic Graph (DAG).

    Args:
        components: List of system component definitions.
        edges: Dependency edges as ``[from_id, to_id]`` pairs.
    """

    components: list[ComponentInput]
    edges: list[tuple[str, str]] = []

    @model_validator(mode="after")
    def validate_dag_input(self) -> DAGInput:
        """Run all cross-field DAG validations after individual fields are set."""
        self._validate_component_count()
        component_ids = self._validate_unique_ids()
        self._validate_edges(component_ids)
        return self

    def _validate_component_count(self) -> None:
        if not self.components:
            raise ValueError("[EMPTY_COMPONENTS] The 'components' list must not be empty.")
        if len(self.components) > MAX_COMPONENTS:
            raise ValueError(
                f"[TOO_MANY_COMPONENTS] DAG has {len(self.components)} components "
                f"which exceeds the maximum of {MAX_COMPONENTS}."
            )

    def _validate_unique_ids(self) -> set[str]:
        seen: dict[str, int] = {}
        for comp in self.components:
            seen[comp.id] = seen.get(comp.id, 0) + 1

        duplicates = {k: v for k, v in seen.items() if v > 1}
        if duplicates:
            raise ValueError(
                f"[DUPLICATE_COMPONENT_ID] Duplicate component IDs found: "
                f"{list(duplicates.keys())}. Each component must have a unique ID."
            )
        return set(seen.keys())

    def _validate_edges(self, component_ids: set[str]) -> None:
        seen_edges: set[tuple[str, str]] = set()

        for from_id, to_id in self.edges:
            # Rule: no self-loops
            if from_id == to_id:
                raise ValueError(
                    f"[SELF_REFERENCING_EDGE] Edge '{from_id}' → '{to_id}' references "
                    f"the same component on both sides. Self-loops are not allowed."
                )

            # Rule: edge IDs must reference existing components
            unknown = [nid for nid in (from_id, to_id) if nid not in component_ids]
            if unknown:
                raise ValueError(
                    f"[EDGE_REFERENCES_UNKNOWN_COMPONENT] Edge '{from_id}' → '{to_id}' "
                    f"references unknown component ID(s): {unknown}"
                )

            # Rule: no duplicate edges
            edge = (from_id, to_id)
            if edge in seen_edges:
                raise ValueError(f"[DUPLICATE_EDGE] Edge '{from_id}' → '{to_id}' appears more than once.")
            seen_edges.add(edge)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ComponentHealth(BaseModel):
    """Health result for a single component.

    Args:
        id: Component identifier.
        name: Component display name.
        type: Component category.
        status: Evaluated health status.
        endpoint: The endpoint that was checked.
        latency_ms: Observed check latency in milliseconds.
        message: Human-readable explanation of the status.
        checked_at: UTC timestamp when the check ran.
        dependencies: IDs of direct dependencies (outgoing edges).
    """

    id: str
    name: str
    type: ComponentType
    status: HealthStatus
    endpoint: str
    latency_ms: float
    message: str
    checked_at: datetime
    dependencies: list[str]


class SystemHealthResponse(BaseModel):
    """Aggregated health result for the entire DAG.

    Args:
        overall_status: Worst status across all components.
        total_components: Total number of components evaluated.
        healthy_count: Number of HEALTHY components.
        degraded_count: Number of DEGRADED components.
        unhealthy_count: Number of UNHEALTHY components.
        components: Individual health results ordered by BFS level.
        evaluation_time_ms: Total time for the full evaluation.
        evaluated_at: UTC timestamp when evaluation started.
        version: API version string.
    """

    overall_status: HealthStatus
    total_components: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    components: list[ComponentHealth]
    evaluation_time_ms: float
    evaluated_at: datetime
    version: str


class LivenessResponse(BaseModel):
    """Response for the GET /health liveness endpoint."""

    status: str
    version: str
    environment: str
    uptime_seconds: float


class DAGVisualizationResponse(BaseModel):
    """Response for base64-encoded DAG image."""

    image_base64: str
    format: str = "png"
    component_count: int
    edge_count: int
