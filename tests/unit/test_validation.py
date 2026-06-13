"""Unit tests for input validation rules in schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.enums import ComponentType
from app.models.schemas import ComponentInput, DAGInput


def make_comp(
    id: str = "svc-1",
    name: str = "My Service",
    type: ComponentType = ComponentType.SERVICE,
    endpoint: str = "http://svc.sim/healthy",
) -> ComponentInput:
    return ComponentInput(id=id, name=name, type=type, endpoint=endpoint)


class TestComponentIdValidation:
    def test_valid_id_accepted(self) -> None:
        c = make_comp(id="my-service_01")
        assert c.id == "my-service_01"

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            make_comp(id="")

    def test_id_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            make_comp(id="a" * 65)

    def test_id_with_spaces_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            make_comp(id="my service")

    def test_id_with_special_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            make_comp(id="step!1")


class TestComponentNameValidation:
    def test_valid_name_accepted(self) -> None:
        c = make_comp(name="My Service Component")
        assert c.name == "My Service Component"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            make_comp(name="")

    def test_whitespace_only_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            make_comp(name="   ")

    def test_name_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            make_comp(name="x" * 129)


class TestEndpointValidation:
    def test_http_endpoint_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.internal/health")
        assert c.endpoint == "http://svc.internal/health"

    def test_https_endpoint_accepted(self) -> None:
        c = make_comp(endpoint="https://svc.internal/health")
        assert c.endpoint == "https://svc.internal/health"

    def test_tcp_endpoint_accepted(self) -> None:
        c = make_comp(endpoint="tcp://db.internal:5432")
        assert c.endpoint == "tcp://db.internal:5432"

    def test_ftp_scheme_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid endpoint scheme"):
            make_comp(endpoint="ftp://bad.example.com")

    def test_no_scheme_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_comp(endpoint="just-a-hostname")

    def test_sim_healthy_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.sim/healthy")
        assert c.is_simulated is True

    def test_sim_unhealthy_accepted(self) -> None:
        c = make_comp(endpoint="tcp://db.sim:5432/unhealthy")
        assert c.is_simulated is True

    def test_sim_degraded_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.sim/degraded")
        assert c.is_simulated is True

    def test_sim_flaky_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.sim/flaky?rate=0.3")
        assert c.is_simulated is True

    def test_sim_slow_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.sim/slow?latency=2000")
        assert c.is_simulated is True

    def test_sim_timeout_accepted(self) -> None:
        c = make_comp(endpoint="http://svc.sim/timeout")
        assert c.is_simulated is True

    def test_sim_invalid_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid simulation path"):
            make_comp(endpoint="http://svc.sim/banana")

    def test_real_endpoint_not_simulated(self) -> None:
        c = make_comp(endpoint="http://real-host.internal/health")
        assert c.is_simulated is False


class TestDAGLevelValidation:
    def test_empty_components_rejected(self) -> None:
        with pytest.raises(ValidationError, match="EMPTY_COMPONENTS"):
            DAGInput(components=[], edges=[])

    def test_too_many_components_rejected(self) -> None:
        comps = [make_comp(id=f"svc-{i}", name=f"Service {i}") for i in range(101)]
        with pytest.raises(ValidationError, match="TOO_MANY_COMPONENTS"):
            DAGInput(components=comps, edges=[])

    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="DUPLICATE_COMPONENT_ID"):
            DAGInput(
                components=[make_comp(id="a"), make_comp(id="a")],
                edges=[],
            )

    def test_self_loop_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SELF_REFERENCING_EDGE"):
            DAGInput(
                components=[make_comp(id="a")],
                edges=[("a", "a")],
            )

    def test_unknown_edge_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="EDGE_REFERENCES_UNKNOWN_COMPONENT"):
            DAGInput(
                components=[make_comp(id="a")],
                edges=[("a", "nonexistent")],
            )

    def test_duplicate_edge_rejected(self) -> None:
        with pytest.raises(ValidationError, match="DUPLICATE_EDGE"):
            DAGInput(
                components=[make_comp(id="a"), make_comp(id="b")],
                edges=[("a", "b"), ("a", "b")],
            )

    def test_valid_dag_accepted(self) -> None:
        dag = DAGInput(
            components=[make_comp(id="a"), make_comp(id="b"), make_comp(id="c")],
            edges=[("a", "b"), ("b", "c")],
        )
        assert len(dag.components) == 3
        assert len(dag.edges) == 2
