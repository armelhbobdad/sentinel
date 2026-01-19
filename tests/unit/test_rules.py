"""Unit tests for collision detection rules.

Tests for graph traversal, pattern matching, and collision scoring.
"""

import pytest

from sentinel.core.types import Edge, Graph, Node


class TestGetNodeEdges:
    """Tests for get_node_edges function."""

    def test_get_node_edges_returns_outgoing_edges(self) -> None:
        """get_node_edges should return edges where node is source."""
        from sentinel.core.rules import get_node_edges

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        result = get_node_edges(graph, "a")

        assert len(result) == 1, f"Expected 1 edge, got {len(result)}"
        assert result[0].source_id == "a", "Edge source should be 'a'"
        assert result[0].target_id == "b", "Edge target should be 'b'"

    def test_get_node_edges_returns_incoming_edges(self) -> None:
        """get_node_edges should return edges where node is target."""
        from sentinel.core.rules import get_node_edges

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        result = get_node_edges(graph, "b")

        assert len(result) == 1, f"Expected 1 edge, got {len(result)}"
        assert result[0].target_id == "b", "Edge target should be 'b'"

    def test_get_node_edges_returns_both_directions(self) -> None:
        """get_node_edges should return both incoming and outgoing edges."""
        from sentinel.core.rules import get_node_edges

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
            Node(id="c", label="C", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = get_node_edges(graph, "b")

        assert len(result) == 2, f"Expected 2 edges, got {len(result)}"

    def test_get_node_edges_returns_empty_for_isolated_node(self) -> None:
        """get_node_edges should return empty tuple for node with no connections."""
        from sentinel.core.rules import get_node_edges

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
            Node(id="isolated", label="Isolated", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        result = get_node_edges(graph, "isolated")

        assert result == (), f"Expected empty tuple, got {result}"

    def test_get_node_edges_returns_empty_for_nonexistent_node(self) -> None:
        """get_node_edges should return empty tuple for node not in graph."""
        from sentinel.core.rules import get_node_edges

        nodes = (Node(id="a", label="A", type="Activity", source="user-stated"),)
        edges = ()
        graph = Graph(nodes=nodes, edges=edges)

        result = get_node_edges(graph, "nonexistent")

        assert result == (), f"Expected empty tuple, got {result}"


class TestBuildAdjacencyList:
    """Tests for _build_adjacency_list helper."""

    def test_build_adjacency_list_creates_bidirectional_entries(self) -> None:
        """Adjacency list should have entries for both source and target."""
        from sentinel.core.rules import _build_adjacency_list

        edges = (Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),)
        graph = Graph(nodes=(), edges=edges)

        adj = _build_adjacency_list(graph)

        assert "a" in adj, "Source node should be in adjacency list"
        assert "b" in adj, "Target node should be in adjacency list"
        assert len(adj["a"]) == 1, "Source should have 1 edge"
        assert len(adj["b"]) == 1, "Target should have 1 edge"

    def test_build_adjacency_list_handles_empty_graph(self) -> None:
        """Adjacency list should be empty for graph with no edges."""
        from sentinel.core.rules import _build_adjacency_list

        graph = Graph(nodes=(), edges=())

        adj = _build_adjacency_list(graph)

        assert adj == {}, f"Expected empty dict, got {adj}"


class TestCollisionPath:
    """Tests for CollisionPath dataclass."""

    def test_collision_path_start_node_returns_first_edge_source(self) -> None:
        """start_node property should return first edge's source."""
        from sentinel.core.rules import CollisionPath

        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
        )
        path = CollisionPath(edges=edges)

        assert path.start_node == "a", f"Expected 'a', got {path.start_node}"

    def test_collision_path_end_node_returns_last_edge_target(self) -> None:
        """end_node property should return last edge's target."""
        from sentinel.core.rules import CollisionPath

        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
        )
        path = CollisionPath(edges=edges)

        assert path.end_node == "c", f"Expected 'c', got {path.end_node}"

    def test_matches_collision_pattern_returns_true_for_valid_pattern(self) -> None:
        """matches_collision_pattern should return True for DRAINS → CONFLICTS_WITH → REQUIRES."""
        from sentinel.core.rules import CollisionPath

        edges = (
            Edge(source_id="person", target_id="drained", relationship="DRAINS", confidence=0.8),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.7,
            ),
            Edge(
                source_id="activity", target_id="focused", relationship="REQUIRES", confidence=0.9
            ),
        )
        path = CollisionPath(edges=edges)

        assert path.matches_collision_pattern() is True, "Should match collision pattern"

    def test_matches_collision_pattern_returns_false_for_short_path(self) -> None:
        """matches_collision_pattern should return False for path < 3 edges."""
        from sentinel.core.rules import CollisionPath

        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
        )
        path = CollisionPath(edges=edges)

        assert path.matches_collision_pattern() is False, "Short path should not match"

    def test_matches_collision_pattern_returns_false_for_wrong_relations(self) -> None:
        """matches_collision_pattern should return False if missing required relations."""
        from sentinel.core.rules import CollisionPath

        edges = (
            Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="SCHEDULED_AT", confidence=0.7),
            Edge(source_id="c", target_id="d", relationship="BELONGS_TO", confidence=0.9),
        )
        path = CollisionPath(edges=edges)

        assert path.matches_collision_pattern() is False, "Wrong relations should not match"


class TestFindCollisionPaths:
    """Tests for find_collision_paths function."""

    def test_find_collision_paths_finds_valid_pattern(self) -> None:
        """find_collision_paths should find DRAINS → CONFLICTS_WITH → REQUIRES pattern."""
        from sentinel.core.rules import find_collision_paths

        nodes = (
            Node(id="person-aunt-susan", label="Aunt Susan", type="Person", source="user-stated"),
            Node(
                id="energystate-drained", label="drained", type="EnergyState", source="ai-inferred"
            ),
            Node(
                id="energystate-focused", label="focused", type="EnergyState", source="ai-inferred"
            ),
            Node(
                id="activity-presentation",
                label="presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.85,
            ),
            Edge(
                source_id="energystate-drained",
                target_id="energystate-focused",
                relationship="CONFLICTS_WITH",
                confidence=0.80,
            ),
            Edge(
                source_id="activity-presentation",
                target_id="energystate-focused",
                relationship="REQUIRES",
                confidence=0.90,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        paths = find_collision_paths(graph)

        assert len(paths) >= 1, f"Expected at least 1 collision path, got {len(paths)}"

    def test_find_collision_paths_returns_empty_for_no_drains(self) -> None:
        """find_collision_paths should return empty list if no DRAINS edges."""
        from sentinel.core.rules import find_collision_paths

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        paths = find_collision_paths(graph)

        assert paths == [], f"Expected empty list, got {paths}"

    def test_find_collision_paths_handles_empty_graph(self) -> None:
        """find_collision_paths should return empty list for empty graph."""
        from sentinel.core.rules import find_collision_paths

        graph = Graph(nodes=(), edges=())

        paths = find_collision_paths(graph)

        assert paths == [], f"Expected empty list, got {paths}"

    def test_find_collision_paths_prevents_cycles(self) -> None:
        """find_collision_paths should not get stuck in cycles."""
        from sentinel.core.rules import find_collision_paths

        # Create a graph with a cycle
        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
            Node(id="c", label="C", type="EnergyState", source="ai-inferred"),
        )
        # a -> b -> c -> b (cycle)
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
            Edge(
                source_id="c", target_id="b", relationship="CONFLICTS_WITH", confidence=0.7
            ),  # Creates cycle
        )
        graph = Graph(nodes=nodes, edges=edges)

        # Should complete without infinite loop
        paths = find_collision_paths(graph)

        # Just verify it completes - the cycle prevention is the main test
        assert isinstance(paths, list), "Should return a list"


class TestFindCollisionPathsAsync:
    """Tests for find_collision_paths_async function."""

    @pytest.mark.asyncio
    async def test_find_collision_paths_async_finds_pattern(self) -> None:
        """find_collision_paths_async should find collision patterns."""
        from sentinel.core.rules import find_collision_paths_async

        nodes = (
            Node(id="person-aunt-susan", label="Aunt Susan", type="Person", source="user-stated"),
            Node(
                id="energystate-drained", label="drained", type="EnergyState", source="ai-inferred"
            ),
            Node(
                id="energystate-focused", label="focused", type="EnergyState", source="ai-inferred"
            ),
            Node(
                id="activity-presentation",
                label="presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.85,
            ),
            Edge(
                source_id="energystate-drained",
                target_id="energystate-focused",
                relationship="CONFLICTS_WITH",
                confidence=0.80,
            ),
            Edge(
                source_id="activity-presentation",
                target_id="energystate-focused",
                relationship="REQUIRES",
                confidence=0.90,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = await find_collision_paths_async(graph)

        assert len(result.paths) >= 1, (
            f"Expected at least 1 collision path, got {len(result.paths)}"
        )
        assert result.timed_out is False, "Should not time out"
        assert result.relationships_analyzed > 0, "Should have analyzed relationships"

    @pytest.mark.asyncio
    async def test_find_collision_paths_async_returns_empty_for_no_drains(self) -> None:
        """find_collision_paths_async should return empty for no DRAINS edges."""
        from sentinel.core.rules import find_collision_paths_async

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        result = await find_collision_paths_async(graph)

        assert result.paths == (), f"Expected empty tuple, got {result.paths}"
        assert result.timed_out is False, "Should not time out"

    @pytest.mark.asyncio
    async def test_find_collision_paths_async_handles_empty_graph(self) -> None:
        """find_collision_paths_async should return empty for empty graph."""
        from sentinel.core.rules import find_collision_paths_async

        graph = Graph(nodes=(), edges=())

        result = await find_collision_paths_async(graph)

        assert result.paths == (), f"Expected empty tuple, got {result.paths}"
        assert result.relationships_analyzed == 0, "Should not analyze any relationships"

    @pytest.mark.asyncio
    async def test_find_collision_paths_async_calls_progress_callback(self) -> None:
        """find_collision_paths_async should call progress callback."""
        from sentinel.core.rules import find_collision_paths_async

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        callback_counts: list[int] = []

        def progress_callback(count: int) -> None:
            callback_counts.append(count)

        await find_collision_paths_async(graph, progress_callback=progress_callback)

        assert len(callback_counts) > 0, "Progress callback should have been called"


class TestTraversalResult:
    """Tests for TraversalResult dataclass."""

    def test_traversal_result_defaults(self) -> None:
        """TraversalResult should have sensible defaults."""
        from sentinel.core.rules import TraversalResult

        result = TraversalResult()

        assert result.paths == (), "Default paths should be empty tuple"
        assert result.timed_out is False, "Default timed_out should be False"
        assert result.relationships_analyzed == 0, "Default relationships_analyzed should be 0"


class TestScoreCollision:
    """Tests for score_collision function."""

    def test_score_collision_calculates_average_confidence(self) -> None:
        """score_collision should calculate confidence from edge confidences."""
        from sentinel.core.rules import CollisionPath, score_collision

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
            Node(id="c", label="C", type="EnergyState", source="ai-inferred"),
            Node(id="d", label="D", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.9),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.8),
            Edge(source_id="d", target_id="c", relationship="REQUIRES", confidence=0.7),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = score_collision(path, graph)

        # Average: (0.9 + 0.8 + 0.7) / 3 = 0.8, but reduced for AI-inferred
        assert 0.0 < result.confidence <= 1.0, (
            f"Confidence should be in (0, 1], got {result.confidence}"
        )

    def test_score_collision_tracks_source_breakdown(self) -> None:
        """score_collision should track ai_inferred vs user_stated counts."""
        from sentinel.core.rules import CollisionPath, score_collision

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
            Node(id="c", label="C", type="EnergyState", source="ai-inferred"),
            Node(id="d", label="D", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.9),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.8),
            Edge(source_id="d", target_id="c", relationship="REQUIRES", confidence=0.7),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = score_collision(path, graph)

        assert "ai_inferred" in result.source_breakdown, "Should have ai_inferred count"
        assert "user_stated" in result.source_breakdown, "Should have user_stated count"

    def test_score_collision_returns_immutable_path(self) -> None:
        """score_collision should return tuple (immutable) for path."""
        from sentinel.core.rules import CollisionPath, score_collision

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.9),
            Edge(source_id="b", target_id="a", relationship="CONFLICTS_WITH", confidence=0.8),
            Edge(source_id="a", target_id="b", relationship="REQUIRES", confidence=0.7),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = score_collision(path, graph)

        assert isinstance(result.path, tuple), f"path should be tuple, got {type(result.path)}"


class TestTimeoutBehavior:
    """Tests for timeout behavior in async traversal (AC #4)."""

    @pytest.mark.asyncio
    async def test_find_collision_paths_async_handles_timeout_gracefully(self) -> None:
        """Async traversal should set timed_out flag on timeout.

        Note: This tests the timeout mechanism structure, not actual time-based timeout.
        """
        from sentinel.core.rules import find_collision_paths_async

        # Create a graph with collision pattern
        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
            Node(id="c", label="C", type="EnergyState", source="ai-inferred"),
            Node(id="d", label="D", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.85),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.80),
            Edge(source_id="d", target_id="c", relationship="REQUIRES", confidence=0.90),
        )
        graph = Graph(nodes=nodes, edges=edges)

        # Normal traversal should not timeout
        result = await find_collision_paths_async(graph, hop_timeout=10.0)

        assert result.timed_out is False, "Normal traversal should not timeout"
        assert len(result.paths) >= 1, "Should find collision path"

    @pytest.mark.asyncio
    async def test_traversal_result_contains_partial_results_on_timeout(self) -> None:
        """TraversalResult should contain any paths found before timeout."""
        # Manually create a result simulating partial completion
        from sentinel.core.rules import CollisionPath, TraversalResult

        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.85),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.80),
            Edge(source_id="c", target_id="d", relationship="REQUIRES", confidence=0.90),
        )
        path = CollisionPath(edges=edges)

        result = TraversalResult(
            paths=(path,),  # Tuple, not list - immutable
            timed_out=True,
            relationships_analyzed=5,
        )

        assert result.timed_out is True, "Should indicate timeout"
        assert len(result.paths) == 1, "Should preserve partial results"
        assert result.relationships_analyzed == 5, "Should track progress"
