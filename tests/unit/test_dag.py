"""Unit tests for DAGService."""

from __future__ import annotations

import pytest

from app.core.exceptions import DAGValidationError
from app.models.enums import ComponentType
from app.models.schemas import ComponentInput, DAGInput
from app.services.dag import DAGService


@pytest.fixture
def svc() -> DAGService:
    return DAGService()


@pytest.fixture
def linear_dag() -> DAGInput:
    """A → B → C (linear chain)."""
    return DAGInput(
        components=[
            ComponentInput(id="a", name="A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy"),
            ComponentInput(id="b", name="B", type=ComponentType.SERVICE, endpoint="http://b.sim/healthy"),
            ComponentInput(id="c", name="C", type=ComponentType.SERVICE, endpoint="http://c.sim/healthy"),
        ],
        edges=[("a", "b"), ("b", "c")],
    )


@pytest.fixture
def diamond_dag() -> DAGInput:
    """A → B, A → C, B → D, C → D (diamond shape, D has 2 parents)."""
    return DAGInput(
        components=[
            ComponentInput(id="a", name="A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy"),
            ComponentInput(id="b", name="B", type=ComponentType.SERVICE, endpoint="http://b.sim/healthy"),
            ComponentInput(id="c", name="C", type=ComponentType.SERVICE, endpoint="http://c.sim/healthy"),
            ComponentInput(id="d", name="D", type=ComponentType.SERVICE, endpoint="http://d.sim/healthy"),
        ],
        edges=[("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )


class TestDAGBuild:
    def test_builds_adjacency_list(self, svc: DAGService, linear_dag: DAGInput) -> None:
        graph, comp_map = svc.build(linear_dag)
        assert "a" in graph
        assert graph["a"] == ["b"]
        assert graph["b"] == ["c"]
        assert graph["c"] == []

    def test_component_map_populated(self, svc: DAGService, linear_dag: DAGInput) -> None:
        _, comp_map = svc.build(linear_dag)
        assert set(comp_map.keys()) == {"a", "b", "c"}
        assert comp_map["a"].name == "A"

    def test_single_node_no_edges(self, svc: DAGService) -> None:
        dag = DAGInput(
            components=[ComponentInput(id="x", name="X", type=ComponentType.SERVICE, endpoint="http://x.sim/healthy")],
            edges=[],
        )
        graph, _ = svc.build(dag)
        assert graph == {"x": []}


class TestCycleDetection:
    def test_valid_dag_no_exception(self, svc: DAGService, linear_dag: DAGInput) -> None:
        graph, _ = svc.build(linear_dag)
        svc.validate_no_cycles(graph)  # Should not raise

    def test_self_loop_rejected_by_schema(self, svc: DAGService) -> None:
        with pytest.raises(Exception):  # Pydantic ValidationError
            DAGInput(
                components=[
                    ComponentInput(id="a", name="A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy")
                ],
                edges=[("a", "a")],
            )

    def test_cycle_raises_dag_validation_error(self, svc: DAGService) -> None:
        dag = DAGInput(
            components=[
                ComponentInput(id="a", name="A", type=ComponentType.SERVICE, endpoint="http://a.sim/healthy"),
                ComponentInput(id="b", name="B", type=ComponentType.SERVICE, endpoint="http://b.sim/healthy"),
                ComponentInput(id="c", name="C", type=ComponentType.SERVICE, endpoint="http://c.sim/healthy"),
            ],
            edges=[("a", "b"), ("b", "c")],
        )
        graph, _ = svc.build(dag)
        # Manually inject a back-edge to create a cycle (bypassing schema validation)
        graph["c"].append("a")

        with pytest.raises(DAGValidationError) as exc_info:
            svc.validate_no_cycles(graph)

        assert exc_info.value.code == "CYCLE_DETECTED"
        assert "cycle_nodes" in exc_info.value.details


class TestRootNodes:
    def test_root_nodes_identified(self, svc: DAGService, linear_dag: DAGInput) -> None:
        graph, _ = svc.build(linear_dag)
        roots = svc.get_root_nodes(graph)
        assert roots == ["a"]

    def test_diamond_has_single_root(self, svc: DAGService, diamond_dag: DAGInput) -> None:
        graph, _ = svc.build(diamond_dag)
        roots = svc.get_root_nodes(graph)
        assert roots == ["a"]

    def test_single_node_is_its_own_root(self, svc: DAGService) -> None:
        dag = DAGInput(
            components=[ComponentInput(id="x", name="X", type=ComponentType.SERVICE, endpoint="http://x.sim/healthy")],
            edges=[],
        )
        graph, _ = svc.build(dag)
        assert svc.get_root_nodes(graph) == ["x"]


class TestBFSLevels:
    def test_linear_bfs_levels(self, svc: DAGService, linear_dag: DAGInput) -> None:
        graph, _ = svc.build(linear_dag)
        levels = svc.bfs_levels(graph)
        assert levels == [["a"], ["b"], ["c"]]

    def test_diamond_bfs_levels(self, svc: DAGService, diamond_dag: DAGInput) -> None:
        graph, _ = svc.build(diamond_dag)
        levels = svc.bfs_levels(graph)
        assert levels[0] == ["a"]
        assert set(levels[1]) == {"b", "c"}
        assert levels[2] == ["d"]

    def test_diamond_d_appears_once(self, svc: DAGService, diamond_dag: DAGInput) -> None:
        """D has two parents — must appear in exactly one BFS level."""
        graph, _ = svc.build(diamond_dag)
        levels = svc.bfs_levels(graph)
        all_nodes = [n for level in levels for n in level]
        assert all_nodes.count("d") == 1
