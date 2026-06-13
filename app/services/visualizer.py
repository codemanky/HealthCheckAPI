"""DAG visualizer: renders a Graphviz diagram coloured by health status."""

from __future__ import annotations

import base64
import typing

import graphviz

from app.core.logging import get_logger
from app.models.enums import HealthStatus

if typing.TYPE_CHECKING:
    from app.models.schemas import ComponentHealth, ComponentInput, DAGInput

logger = get_logger(__name__)

# Warm color palette — no blue tones
_STATUS_COLORS: dict[HealthStatus, dict[str, str]] = {
    HealthStatus.HEALTHY: {"fill": "#2ecc71", "font": "#ffffff", "border": "#27ae60"},
    HealthStatus.DEGRADED: {"fill": "#f39c12", "font": "#ffffff", "border": "#e67e22"},
    HealthStatus.UNHEALTHY: {"fill": "#e74c3c", "font": "#ffffff", "border": "#c0392b"},
    HealthStatus.UNKNOWN: {"fill": "#95a5a6", "font": "#ffffff", "border": "#7f8c8d"},
}

_EDGE_COLOR = "#2c3e50"
_EDGE_COLOR_FAILED = "#e74c3c"
_BG_COLOR = "#ffffff"
_GRAPH_FONT = "Helvetica"


class DAGVisualizer:
    """Renders a DAG as a PNG image coloured by component health status.

    Healthy components are green, degraded are amber, unhealthy are red.
    Edges that lead to unhealthy components are drawn in dashed red.
    """

    def render(
        self,
        dag_input: DAGInput,
        health_results: list[ComponentHealth] | None = None,
    ) -> bytes:
        """Generate a PNG image of the DAG.

        Args:
            dag_input: The DAG structure (components + edges).
            health_results: Optional health results to colour nodes.
                            If None, all nodes are rendered as UNKNOWN.

        Returns:
            PNG image as raw bytes.
        """
        # Build a status lookup
        status_map: dict[str, HealthStatus] = {}
        if health_results:
            status_map = {r.id: r.status for r in health_results}

        unhealthy_ids = {cid for cid, s in status_map.items() if s == HealthStatus.UNHEALTHY}

        dot = graphviz.Digraph(
            name="HealthCheckDAG",
            format="png",
        )
        dot.attr(
            bgcolor=_BG_COLOR,
            fontname=_GRAPH_FONT,
            fontsize="12",
            rankdir="LR",  # left-to-right layout
            splines="ortho",
            nodesep="0.6",
            ranksep="1.0",
        )
        dot.attr(
            "node",
            fontname=_GRAPH_FONT,
            fontsize="11",
            style="filled,rounded",
            shape="box",
            margin="0.3,0.15",
            penwidth="1.5",
        )
        dot.attr(
            "edge",
            fontname=_GRAPH_FONT,
            fontsize="9",
            penwidth="1.5",
            arrowsize="0.8",
        )

        # Add nodes
        {c.id: c for c in dag_input.components}
        for comp in dag_input.components:
            status = status_map.get(comp.id, HealthStatus.UNKNOWN)
            colors = _STATUS_COLORS[status]
            label = self._node_label(comp, status)

            dot.node(
                comp.id,
                label=label,
                fillcolor=colors["fill"],
                fontcolor=colors["font"],
                color=colors["border"],
            )

        # Add edges
        for from_id, to_id in dag_input.edges:
            is_failed_edge = to_id in unhealthy_ids
            dot.edge(
                from_id,
                to_id,
                color=_EDGE_COLOR_FAILED if is_failed_edge else _EDGE_COLOR,
                style="dashed" if is_failed_edge else "solid",
                penwidth="2.0" if is_failed_edge else "1.5",
            )

        logger.info(
            "Rendering DAG visualization",
            nodes=len(dag_input.components),
            edges=len(dag_input.edges),
            unhealthy_nodes=len(unhealthy_ids),
        )

        return typing.cast("bytes", dot.pipe(format="png"))

    def render_base64(
        self,
        dag_input: DAGInput,
        health_results: list[ComponentHealth] | None = None,
    ) -> str:
        """Render the DAG and return the PNG encoded as a base64 string.

        Args:
            dag_input: DAG structure.
            health_results: Optional health results for colouring.

        Returns:
            Base64-encoded PNG string.
        """
        png_bytes = self.render(dag_input, health_results)
        return base64.b64encode(png_bytes).decode("utf-8")

    @staticmethod
    def _node_label(comp: ComponentInput, status: HealthStatus) -> str:
        """Build the Graphviz label for a node.

        Shows component name, type, and status emoji on two lines.
        """
        status_icon = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.DEGRADED: "⚠",
            HealthStatus.UNHEALTHY: "✗",
            HealthStatus.UNKNOWN: "?",
        }[status]

        return f"{status_icon} {comp.name}\n[{comp.type.value}] {status.value.upper()}"
