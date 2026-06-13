"""Core health check orchestration: builds DAG, evaluates components, aggregates results."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.enums import HealthStatus
from app.models.schemas import (
    ComponentHealth,
    ComponentInput,
    DAGInput,
    SystemHealthResponse,
)
from app.observability.metrics import (
    DAG_EVALUATION_DURATION,
    record_component_health,
)
from app.services.checks.factory import get_check_strategy
from app.services.dag import DAGService, Graph

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

import contextlib

@contextlib.contextmanager
def optional_span(name: str, **kwargs):
    if tracer:
        with tracer.start_as_current_span(name, **kwargs) as span:
            yield span
    else:
        yield None

logger = get_logger(__name__)

# Status priority: higher index = worse health
_STATUS_PRIORITY: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.UNHEALTHY: 3,
}


def _worst_status(*statuses: HealthStatus) -> HealthStatus:
    """Return the most severe HealthStatus from the given statuses."""
    return max(statuses, key=lambda s: _STATUS_PRIORITY[s])


class HealthCheckerService:
    """Orchestrates asynchronous health evaluation of all DAG components.

    Evaluation flow:
    1. Build adjacency list from DAGInput.
    2. Validate no cycles (Kahn's algorithm).
    3. BFS level traversal — nodes at the same level run concurrently.
    4. After each level, propagate health upward: if a dependency is
       UNHEALTHY, its parent is at best DEGRADED.
    5. Aggregate overall status (worst status wins).
    6. Emit structured log table and Prometheus metrics.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._dag = DAGService()
        self._settings = settings or get_settings()

    async def evaluate(self, dag_input: DAGInput) -> SystemHealthResponse:
        """Evaluate the health of every component in the DAG.

        Args:
            dag_input: Validated DAG input (components + edges).

        Returns:
            Aggregated ``SystemHealthResponse`` with per-component results.
        """
        started_at = datetime.now(UTC)
        wall_start = time.monotonic()

        graph, component_map = self._dag.build(dag_input)
        self._dag.validate_no_cycles(graph)

        # Warn (don't reject) on disconnected graphs
        if not self._dag.check_connectivity(graph):
            logger.warning(
                "DAG is not fully connected — processing all subgraphs independently"
            )

        bfs_levels = self._dag.bfs_levels(graph)
        # Evaluate in reverse BFS order: leaves first, then their dependents.
        # This ensures every dependency has a result before its dependent is checked,
        # enabling correct health propagation (unhealthy dep → degrade parent).
        eval_order = list(reversed(bfs_levels))

        # Track results keyed by component ID
        results: dict[str, ComponentHealth] = {}
        
        async def _eval_loop() -> None:
            for level_idx, level_nodes in enumerate(eval_order):
                logger.debug(
                    "Evaluating BFS level (bottom-up)",
                    level=level_idx,
                    nodes=level_nodes,
                )

                # Run all checks in this level concurrently
                tasks = [
                    self._check_component(
                        component_map[node_id],
                        graph,
                        results,
                    )
                    for node_id in level_nodes
                ]
                level_results: list[ComponentHealth | BaseException] = (
                    await asyncio.gather(*tasks, return_exceptions=True)
                )

                for node_id, result in zip(level_nodes, level_results, strict=True):
                    if isinstance(result, BaseException):
                        # Should not happen — _check_component catches all errors
                        comp = component_map[node_id]
                        results[node_id] = ComponentHealth(
                            id=comp.id,
                            name=comp.name,
                            type=comp.type,
                            status=HealthStatus.UNKNOWN,
                            endpoint=comp.endpoint,
                            latency_ms=0.0,
                            message=f"Unexpected error: {result}",
                            checked_at=datetime.now(UTC),
                            dependencies=self._dag.get_dependencies(graph, node_id),
                        )
                    else:
                        results[node_id] = result

        timeout_occurred = False
        with optional_span("dag.evaluate"):
            try:
                await asyncio.wait_for(
                    _eval_loop(), timeout=self._settings.evaluation_timeout_seconds
                )
            except asyncio.TimeoutError:
                timeout_occurred = True
                logger.error("Overall evaluation timed out", timeout=self._settings.evaluation_timeout_seconds)
                # Fill remaining components with UNKNOWN
                for node_id, comp in component_map.items():
                    if node_id not in results:
                        results[node_id] = ComponentHealth(
                            id=comp.id,
                            name=comp.name,
                            type=comp.type,
                            status=HealthStatus.UNKNOWN,
                            endpoint=comp.endpoint,
                            latency_ms=0.0,
                            message=f"Evaluation timed out after {self._settings.evaluation_timeout_seconds}s",
                            checked_at=datetime.now(UTC),
                            dependencies=self._dag.get_dependencies(graph, node_id),
                        )

        # Collect results in BFS (top-down) order for the response
        ordered_results = [
            results[node_id]
            for level in bfs_levels
            for node_id in level
            if node_id in results
        ]

        # Record per-component Prometheus metrics
        for r in ordered_results:
            record_component_health(
                component_id=r.id,
                component_name=r.name,
                component_type=r.type.value,
                status=r.status.value,
                latency_seconds=r.latency_ms / 1000.0,
            )

        # Aggregate counts
        status_counts = {s: 0 for s in HealthStatus}
        for r in ordered_results:
            status_counts[r.status] += 1

        overall = _worst_status(*[r.status for r in ordered_results]) if ordered_results else HealthStatus.UNKNOWN
        if timeout_occurred:
            overall = HealthStatus.UNHEALTHY

        evaluation_time_ms = (time.monotonic() - wall_start) * 1000

        # Record DAG evaluation duration metric
        DAG_EVALUATION_DURATION.observe(evaluation_time_ms / 1000.0)

        self._log_results_table(ordered_results, overall, evaluation_time_ms)

        return SystemHealthResponse(
            overall_status=overall,
            total_components=len(ordered_results),
            healthy_count=status_counts[HealthStatus.HEALTHY],
            degraded_count=status_counts[HealthStatus.DEGRADED],
            unhealthy_count=status_counts[HealthStatus.UNHEALTHY],
            components=ordered_results,
            evaluation_time_ms=round(evaluation_time_ms, 2),
            evaluated_at=started_at,
            version=self._settings.app_version,
        )

    async def _check_component(
        self,
        component: ComponentInput,
        graph: Graph,
        existing_results: dict[str, ComponentHealth],
    ) -> ComponentHealth:
        """Run a single component check, applying dependency-based health propagation.

        If any direct dependency is UNHEALTHY, the component's status is at best
        DEGRADED (propagation rule: a component cannot be HEALTHY if it depends
        on an unhealthy component).

        Args:
            component: Component to check.
            graph: Full DAG adjacency list.
            existing_results: Already-evaluated component results.

        Returns:
            ComponentHealth with status potentially degraded by dependency health.
        """
        dep_ids = self._dag.get_dependencies(graph, component.id)

        with optional_span(f"health_check.{component.id}", attributes={
            "component.id": component.id,
            "component.type": component.type.value,
        }) as span:
            # Check actual health
            strategy = get_check_strategy(component, self._settings)
            result = await strategy.check(component, dep_ids)

            if span:
                span.set_attribute("health.status", result.status.value)
                span.set_attribute("health.latency_ms", result.latency_ms)

            # Health propagation: apply dependency penalty
            propagated_status = self._propagate_health(result.status, dep_ids, existing_results)

        if propagated_status != result.status:
            logger.info(
                "Health propagated from dependency",
                component_id=component.id,
                original_status=result.status.value,
                propagated_status=propagated_status.value,
                unhealthy_deps=[
                    d for d in dep_ids
                    if existing_results.get(d, ComponentHealth(
                        id=d, name=d, type=component.type,
                        status=HealthStatus.UNKNOWN, endpoint="",
                        latency_ms=0, message="", checked_at=datetime.now(UTC),
                        dependencies=[]
                    )).status == HealthStatus.UNHEALTHY
                ],
            )
            result = result.model_copy(
                update={
                    "status": propagated_status,
                    "message": (
                        result.message
                        + " [degraded due to unhealthy dependency]"
                    ),
                }
            )

        return result

    def _propagate_health(
        self,
        own_status: HealthStatus,
        dep_ids: list[str],
        existing_results: dict[str, ComponentHealth],
    ) -> HealthStatus:
        """Apply upstream health propagation rule.

        Rule depends on settings.propagation_mode:
        - strict: unhealthy dep -> parent DEGRADED
        - lenient: unhealthy dep -> parent keeps own status (just annotated)
        - none: no propagation

        Args:
            own_status: This component's own check status.
            dep_ids: Direct dependency IDs.
            existing_results: Already-evaluated results.

        Returns:
            Final status after propagation.
        """
        if self._settings.propagation_mode == "none":
            return own_status

        has_unhealthy_dep = any(
            existing_results[d].status == HealthStatus.UNHEALTHY
            for d in dep_ids
            if d in existing_results
        )

        if has_unhealthy_dep and own_status == HealthStatus.HEALTHY:
            if self._settings.propagation_mode == "strict":
                return HealthStatus.DEGRADED

        return own_status

    def _log_results_table(
        self,
        results: list[ComponentHealth],
        overall: HealthStatus,
        evaluation_time_ms: float,
    ) -> None:
        """Emit a structured ASCII table of health results to the log."""
        col_widths = {"name": 28, "type": 10, "status": 10, "latency": 10, "message": 40}
        sep = "-" * (sum(col_widths.values()) + len(col_widths) * 3 + 1)

        lines = [
            "",
            "╔══════════════════════════════════════╗",
            "║       SYSTEM HEALTH CHECK RESULTS     ║",
            "╚══════════════════════════════════════╝",
            sep,
            f"  {'Component':<{col_widths['name']}} {'Type':<{col_widths['type']}} {'Status':<{col_widths['status']}} {'Latency(ms)':<{col_widths['latency']}} {'Message':<{col_widths['message']}}",
            sep,
        ]

        for r in results:
            lines.append(
                f"  {r.name:<{col_widths['name']}} "
                f"{r.type.value:<{col_widths['type']}} "
                f"{r.status.value.upper():<{col_widths['status']}} "
                f"{r.latency_ms:<{col_widths['latency']}.1f} "
                f"{r.message[:col_widths['message']]:<{col_widths['message']}}"
            )

        lines += [
            sep,
            f"  Overall: {overall.value.upper()}  |  "
            f"Evaluated {len(results)} components in {evaluation_time_ms:.0f}ms",
            sep,
            "",
        ]

        logger.info("Health check summary", table="\n".join(lines))
