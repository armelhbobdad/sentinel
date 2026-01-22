"""Tests for graph operations module.

Tests the extract_neighborhood and find_node_by_label functions.
"""

import time

import pytest

from sentinel.core.graph_ops import extract_neighborhood
from sentinel.core.types import Edge, Graph, Node


class TestExtractNeighborhoodDepth:
    """Tests for neighborhood extraction at various depths."""

    def test_extract_neighborhood_depth_0_returns_focal_only(self) -> None:
        """Depth 0 returns only the focal node."""
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
            ),
            edges=(Edge(source_id="1", target_id="2", relationship="KNOWS", confidence=0.9),),
        )
        focal = graph.nodes[0]

        result = extract_neighborhood(graph, focal, depth=0)

        assert len(result.nodes) == 1, f"Expected 1 node, got {len(result.nodes)}"
        assert result.nodes[0].label == "A"
        assert len(result.edges) == 0, f"Expected 0 edges, got {len(result.edges)}"

    def test_extract_neighborhood_depth_1_includes_direct_connections(self) -> None:
        """Depth 1 includes focal node and immediate neighbors."""
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
                Node(id="3", label="C", type="Person", source="ai-inferred"),
            ),
            edges=(
                Edge(source_id="1", target_id="2", relationship="KNOWS", confidence=0.9),
                Edge(source_id="2", target_id="3", relationship="DRAINS", confidence=0.8),
            ),
        )
        focal = graph.nodes[0]  # A

        result = extract_neighborhood(graph, focal, depth=1)

        labels = {n.label for n in result.nodes}
        assert labels == {"A", "B"}, f"Expected {{'A', 'B'}}, got {labels}"

    def test_extract_neighborhood_depth_2_traverses_two_hops(self) -> None:
        """Depth 2 includes nodes up to 2 hops away."""
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
                Node(id="3", label="C", type="Person", source="ai-inferred"),
            ),
            edges=(
                Edge(source_id="1", target_id="2", relationship="KNOWS", confidence=0.9),
                Edge(source_id="2", target_id="3", relationship="DRAINS", confidence=0.8),
            ),
        )
        focal = graph.nodes[0]  # A

        result = extract_neighborhood(graph, focal, depth=2)

        labels = {n.label for n in result.nodes}
        assert labels == {"A", "B", "C"}, f"Expected {{'A', 'B', 'C'}}, got {labels}"


class TestExtractNeighborhoodEdges:
    """Tests for edge inclusion in neighborhood extraction."""

    def test_extract_neighborhood_includes_all_edges_between_nodes(self) -> None:
        """All edges between neighborhood nodes are included."""
        # A -> B (1 hop), B -> C (2 hops from A), no direct A->C edge
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
                Node(id="3", label="C", type="Person", source="ai-inferred"),
            ),
            edges=(
                Edge(source_id="1", target_id="2", relationship="KNOWS", confidence=0.9),
                Edge(source_id="2", target_id="3", relationship="DRAINS", confidence=0.8),
            ),
        )
        focal = graph.nodes[0]

        result = extract_neighborhood(graph, focal, depth=1)

        # A, B are in neighborhood at depth 1; C is at depth 2
        # Only edge A->B should be included (B->C crosses out of neighborhood)
        labels = {n.label for n in result.nodes}
        assert labels == {"A", "B"}, f"Expected {{'A', 'B'}}, got {labels}"
        assert len(result.edges) == 1, f"Expected 1 edge, got {len(result.edges)}"
        assert result.edges[0].relationship == "KNOWS"

    def test_extract_neighborhood_excludes_edges_outside_neighborhood(self) -> None:
        """Edges to nodes outside the neighborhood are excluded."""
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
                Node(id="3", label="C", type="Person", source="ai-inferred"),
                Node(id="4", label="D", type="Person", source="ai-inferred"),
            ),
            edges=(
                Edge(source_id="1", target_id="2", relationship="KNOWS", confidence=0.9),
                Edge(source_id="3", target_id="4", relationship="DRAINS", confidence=0.8),
            ),
        )
        focal = graph.nodes[0]  # A

        result = extract_neighborhood(graph, focal, depth=1)

        # Only A->B edge should be included, not C->D
        assert len(result.edges) == 1
        rels = {e.relationship for e in result.edges}
        assert "KNOWS" in rels
        assert "DRAINS" not in rels


class TestExtractNeighborhoodEdgeCases:
    """Tests for edge cases in neighborhood extraction."""

    def test_extract_neighborhood_disconnected_node(self) -> None:
        """Focal node with no edges returns just the focal node."""
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
            ),
            edges=(),  # No edges
        )
        focal = graph.nodes[0]

        result = extract_neighborhood(graph, focal, depth=2)

        assert len(result.nodes) == 1
        assert result.nodes[0].label == "A"
        assert len(result.edges) == 0

    def test_extract_neighborhood_self_loop(self) -> None:
        """Self-loop edges are handled correctly."""
        graph = Graph(
            nodes=(Node(id="1", label="A", type="Person", source="user-stated"),),
            edges=(Edge(source_id="1", target_id="1", relationship="REFLECTS", confidence=0.5),),
        )
        focal = graph.nodes[0]

        result = extract_neighborhood(graph, focal, depth=1)

        assert len(result.nodes) == 1
        assert len(result.edges) == 1
        assert result.edges[0].relationship == "REFLECTS"

    def test_extract_neighborhood_bidirectional_traversal(self) -> None:
        """Neighborhood includes nodes reachable by incoming edges."""
        # A <- B means B should be in A's neighborhood (undirected traversal)
        graph = Graph(
            nodes=(
                Node(id="1", label="A", type="Person", source="user-stated"),
                Node(id="2", label="B", type="Person", source="ai-inferred"),
            ),
            edges=(Edge(source_id="2", target_id="1", relationship="DRAINS", confidence=0.9),),
        )
        focal = graph.nodes[0]  # A (target of edge)

        result = extract_neighborhood(graph, focal, depth=1)

        labels = {n.label for n in result.nodes}
        assert labels == {"A", "B"}, f"Expected {{'A', 'B'}}, got {labels}"

    def test_extract_neighborhood_negative_depth_raises_error(self) -> None:
        """Negative depth raises ValueError."""
        graph = Graph(
            nodes=(Node(id="1", label="A", type="Person", source="user-stated"),),
            edges=(),
        )
        focal = graph.nodes[0]

        with pytest.raises(ValueError, match="Depth must be non-negative"):
            extract_neighborhood(graph, focal, depth=-1)


class TestExtractNeighborhoodPerformance:
    """Performance tests for neighborhood extraction."""

    def test_extract_neighborhood_performance_under_3_seconds(self) -> None:
        """Neighborhood extraction completes within NFR4 (3 seconds)."""
        # Create a moderately large graph (50 nodes, 100 edges)
        nodes = tuple(
            Node(id=str(i), label=f"Node{i}", type="Entity", source="ai-inferred")
            for i in range(50)
        )
        edges = tuple(
            Edge(
                source_id=str(i % 50),
                target_id=str((i + 1) % 50),
                relationship="RELATES",
                confidence=0.8,
            )
            for i in range(100)
        )
        graph = Graph(nodes=nodes, edges=edges)
        focal = nodes[0]

        start = time.time()
        extract_neighborhood(graph, focal, depth=2)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Extraction took {elapsed:.2f}s, expected < 3s"

    def test_extract_neighborhood_large_graph_depth_2(self) -> None:
        """Handles larger graphs efficiently."""
        # 100 nodes, 200 edges
        nodes = tuple(
            Node(id=str(i), label=f"Node{i}", type="Entity", source="ai-inferred")
            for i in range(100)
        )
        edges = tuple(
            Edge(
                source_id=str(i % 100),
                target_id=str((i + 1) % 100),
                relationship="RELATES",
                confidence=0.8,
            )
            for i in range(200)
        )
        graph = Graph(nodes=nodes, edges=edges)
        focal = nodes[0]

        start = time.time()
        result = extract_neighborhood(graph, focal, depth=2)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Extraction took {elapsed:.2f}s, expected < 3s"
        assert len(result.nodes) > 0
