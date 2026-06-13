"""E2E API tests using AsyncClient against the full FastAPI app."""

from __future__ import annotations

from httpx import AsyncClient
from typing import Any

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.asyncio
class TestLivenessEndpoint:
    async def test_liveness_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_liveness_response_schema(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "environment" in body
        assert "uptime_seconds" in body


@pytest.mark.asyncio
class TestEvaluateEndpoint:
    async def test_evaluate_sample_dag_returns_200(self, client: AsyncClient) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 200

    async def test_evaluate_response_schema(self, client: AsyncClient) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
        response = await client.post("/health/evaluate", json=payload)
        body = response.json()

        assert "overall_status" in body
        assert "total_components" in body
        assert "components" in body
        assert isinstance(body["components"], list)
        assert body["total_components"] == 11

    async def test_evaluate_returns_all_components(self, client: AsyncClient) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
        response = await client.post("/health/evaluate", json=payload)
        body = response.json()
        result_ids = {c["id"] for c in body["components"]}
        expected_ids = {f"step-{i}" for i in range(1, 12)}
        assert result_ids == expected_ids

    async def test_empty_components_returns_422(self, client: AsyncClient) -> None:
        payload: dict[str, Any] = {"components": [], "edges": []}
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 422

    async def test_duplicate_ids_returns_422(self, client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "components": [
                {"id": "a", "name": "A", "type": "service", "endpoint": "http://a.sim/healthy"},
                {"id": "a", "name": "A2", "type": "service", "endpoint": "http://a2.sim/healthy"},
            ],
            "edges": [],
        }
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 422

    async def test_invalid_endpoint_scheme_returns_422(self, client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "components": [
                {"id": "a", "name": "A", "type": "service", "endpoint": "ftp://bad.example"},
            ],
            "edges": [],
        }
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 422

    async def test_unknown_edge_reference_returns_422(self, client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "components": [
                {"id": "a", "name": "A", "type": "service", "endpoint": "http://a.sim/healthy"},
            ],
            "edges": [["a", "nonexistent"]],
        }
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 422

    async def test_self_loop_returns_422(self, client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "components": [
                {"id": "a", "name": "A", "type": "service", "endpoint": "http://a.sim/healthy"},
            ],
            "edges": [["a", "a"]],
        }
        response = await client.post("/health/evaluate", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
class TestVisualizeEndpoint:
    async def test_visualize_returns_png(self, client: AsyncClient) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
        response = await client.post("/dag/visualize", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert response.content[:4] == b"\x89PNG"

    async def test_visualize_base64_format(self, client: AsyncClient) -> None:
        payload = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
        response = await client.post("/dag/visualize?format=base64", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "image_base64" in body
        assert body["format"] == "png"
        assert body["component_count"] == 11
        assert body["edge_count"] == 11
