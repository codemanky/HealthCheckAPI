"""DAG construction, validation, and traversal algorithms."""

from __future__ import annotations

from collections import deque

from app.core.exceptions import DAGValidationError
from app.core.logging import get_logger
from app.models.schemas import ComponentInput, DAGInput

logger = get_logger(__name__)

# Adjacency list type: node_id -> list of dependency IDs
Graph = dict[str, list[str]]


class DAGService:
    """Builds and traverses a Directed Acyclic Graph of system components.

    The graph is directed: an edge (A → B) means A depends on B.
    Edges are stored as an adjacency list mapping each node to its dependencies.
    """

    def build(self, dag_input: DAGInput) -> tuple[Graph, dict[str, ComponentInput]]:
        """Construct an adjacency list and component lookup from DAGInput.

        Args:
            dag_input: Validated DAG input containing components and edges.

        Returns:
            A tuple of (graph, component_map) where graph maps each component ID
            to its list of dependency IDs, and component_map maps ID to ComponentInput.
        """
        component_map: dict[str, ComponentInput] = {c.id: c for c in dag_input.components}

        # Initialise every node with an empty dependency list
        graph: Graph = {c.id: [] for c in dag_input.components}

        for from_id, to_id in dag_input.edges:
            graph[from_id].append(to_id)

        logger.info(
            "DAG built",
            nodes=len(graph),
            edges=len(dag_input.edges),
        )
        return graph, component_map

    def validate_no_cycles(self, graph: Graph) -> None:
        """Verify the graph is acyclic using Kahn's topological sort algorithm.

        Raises:
            DAGValidationError: If a cycle is detected, with the error code
                ``CYCLE_DETECTED`` and the cycle path in details.
        """
        in_degree: dict[str, int] = {node: 0 for node in graph}
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue: deque[str] = deque(node for node, deg in in_degree.items() if deg == 0)
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for dep in graph.get(node, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        if visited_count != len(graph):
            # Nodes not reached are part of a cycle
            cycle_nodes = [n for n in graph if in_degree[n] > 0]
            raise DAGValidationError(
                code="CYCLE_DETECTED",
                message=(
                    f"The graph contains a cycle involving nodes: {cycle_nodes}. "
                    "Only Directed Acyclic Graphs (DAGs) are supported."
                ),
                details={"cycle_nodes": cycle_nodes},
            )

    def get_root_nodes(self, graph: Graph) -> list[str]:
        """Return all nodes with no incoming edges (zero in-degree).

        These are the entry points of the DAG — components with no dependents.

        Args:
            graph: Adjacency list mapping node → dependencies.

        Returns:
            List of root node IDs.
        """
        all_deps: set[str] = {dep for deps in graph.values() for dep in deps}
        roots = [node for node in graph if node not in all_deps]
        logger.debug("Root nodes identified", roots=roots)
        return roots

    def bfs_levels(self, graph: Graph) -> list[list[str]]:
        """Perform BFS and return nodes grouped by level (breadth-first order).

        Nodes at the same level have no dependency between them and can be
        health-checked concurrently.

        Args:
            graph: Adjacency list mapping node → dependencies.

        Returns:
            List of lists, each inner list is one BFS level.
            Example: [[root1, root2], [child_a, child_b], [leaf]]
        """
        root_nodes = self.get_root_nodes(graph)
        if not root_nodes:
            return []

        visited: set[str] = set()
        levels: list[list[str]] = []
        current_level = list(root_nodes)
        queued: set[str] = set(root_nodes)  # tracks nodes already scheduled

        while current_level:
            # Only include nodes not yet visited (handles diamond/multi-parent cases)
            unique_level = [n for n in current_level if n not in visited]
            if not unique_level:
                break

            levels.append(unique_level)
            visited.update(unique_level)

            next_level: list[str] = []
            for node in unique_level:
                for dep in graph.get(node, []):
                    if dep not in visited and dep not in queued:
                        next_level.append(dep)
                        queued.add(dep)
            current_level = next_level

        logger.debug(
            "BFS traversal complete",
            levels=len(levels),
            level_sizes=[len(lvl) for lvl in levels],
        )
        return levels

    def get_dependencies(self, graph: Graph, node_id: str) -> list[str]:
        """Return direct dependency IDs for a given node.

        Args:
            graph: Adjacency list.
            node_id: The node to look up.

        Returns:
            List of direct dependency IDs.
        """
        return graph.get(node_id, [])

    def check_connectivity(self, graph: Graph) -> bool:
        """Check if all nodes in the graph are reachable from root nodes.

        Args:
            graph: Adjacency list.

        Returns:
            True if fully connected, False if there are isolated subgraphs.
        """
        if not graph:
            return True

        reachable: set[str] = set()
        queue: deque[str] = deque(self.get_root_nodes(graph))
        while queue:
            node = queue.popleft()
            if node in reachable:
                continue
            reachable.add(node)
            for dep in graph.get(node, []):
                queue.append(dep)

        return reachable == set(graph.keys())
