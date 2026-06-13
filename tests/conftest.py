"""Shared test fixtures and configuration."""

from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.enums import ComponentType
from app.models.schemas import ComponentInput, DAGInput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_dag_input() -> DAGInput:
    """Load the sample DAG from the fixture file."""
    data = json.loads((FIXTURES_DIR / "sample_dag.json").read_text())
    return DAGInput.model_validate(data)


@pytest.fixture
def simple_healthy_dag() -> DAGInput:
    """A minimal 3-node fully healthy DAG for basic testing."""
    return DAGInput(
        components=[
            ComponentInput(id="a", name="Service A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy"),
            ComponentInput(id="b", name="Service B", type=ComponentType.SERVICE, endpoint="http://b.sim/healthy"),
            ComponentInput(id="c", name="Service C", type=ComponentType.DATABASE, endpoint="tcp://c.sim:5432/healthy"),
        ],
        edges=[("a", "b"), ("b", "c")],
    )


@pytest.fixture
def dag_with_failure() -> DAGInput:
    """A 3-node DAG where the leaf node is unhealthy."""
    return DAGInput(
        components=[
            ComponentInput(id="a", name="Service A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy"),
            ComponentInput(id="b", name="Service B", type=ComponentType.SERVICE, endpoint="http://b.sim/healthy"),
            ComponentInput(id="c", name="Database", type=ComponentType.DATABASE, endpoint="tcp://c.sim:5432/unhealthy"),
        ],
        edges=[("a", "b"), ("b", "c")],
    )


@pytest_asyncio.fixture
async def client() -> typing.AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI app."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
