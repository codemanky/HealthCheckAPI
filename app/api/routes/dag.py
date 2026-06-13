"""DAG visualization API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import get_health_checker, get_visualizer
from app.models.schemas import DAGInput, DAGVisualizationResponse, SystemHealthResponse
from app.services.health_checker import HealthCheckerService
from app.services.visualizer import DAGVisualizer

router = APIRouter(tags=["DAG Visualization"])


@router.post(
    "/dag/visualize",
    summary="Visualize DAG as image",
    description=(
        "Renders the component DAG as a PNG image.\n\n"
        "Optionally performs a health evaluation first and colours nodes by status:\n"
        "- 🟢 Green: HEALTHY\n"
        "- 🟡 Amber: DEGRADED\n"
        "- 🔴 Red: UNHEALTHY\n"
        "- ⬜ Gray: UNKNOWN\n\n"
        "Edges leading to unhealthy components are drawn as dashed red lines.\n\n"
        "Use `?format=base64` to receive a JSON response with the base64-encoded "
        "image instead of a raw PNG."
    ),
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "PNG image of the DAG",
        }
    },
)
async def visualize_dag(
    dag_input: DAGInput,
    evaluate: bool = Query(
        default=True,
        description="Run health evaluation before rendering to colour nodes by status.",
    ),
    format: str = Query(
        default="png",
        description="Response format: 'png' (binary) or 'base64' (JSON).",
    ),
    checker: HealthCheckerService = Depends(get_health_checker),
    visualizer: DAGVisualizer = Depends(get_visualizer),
) -> Response:
    """POST /dag/visualize — render DAG as PNG, optionally coloured by health status."""
    health_results = None
    if evaluate:
        result: SystemHealthResponse = await checker.evaluate(dag_input)
        health_results = result.components

    if format == "base64":
        b64 = visualizer.render_base64(dag_input, health_results)
        return Response(
            content=DAGVisualizationResponse(
                image_base64=b64,
                format="png",
                component_count=len(dag_input.components),
                edge_count=len(dag_input.edges),
            ).model_dump_json(),
            media_type="application/json",
        )

    png_bytes = visualizer.render(dag_input, health_results)
    return Response(content=png_bytes, media_type="image/png")
