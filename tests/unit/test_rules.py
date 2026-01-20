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


class TestClassifyDomain:
    """Tests for classify_domain function (Story 2.2)."""

    def test_classify_domain_person_family_returns_social(self) -> None:
        """classify_domain should return SOCIAL for family members."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="person-aunt-susan",
            label="Aunt Susan",
            type="Person",
            source="user-stated",
            metadata={"relationship": "family"},
        )

        result = classify_domain(node)

        assert result == Domain.SOCIAL, f"Expected SOCIAL, got {result}"

    def test_classify_domain_activity_dinner_returns_social(self) -> None:
        """classify_domain should return SOCIAL for dinner activities."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-dinner",
            label="Dinner with Aunt Susan",
            type="Activity",
            source="user-stated",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.SOCIAL, f"Expected SOCIAL, got {result}"

    def test_classify_domain_activity_presentation_returns_professional(self) -> None:
        """classify_domain should return PROFESSIONAL for work activities."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-presentation",
            label="Strategy Presentation",
            type="Activity",
            source="user-stated",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.PROFESSIONAL, f"Expected PROFESSIONAL, got {result}"

    def test_classify_domain_activity_meeting_returns_professional(self) -> None:
        """classify_domain should return PROFESSIONAL for meeting activities."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-meeting",
            label="Client Meeting",
            type="Activity",
            source="user-stated",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.PROFESSIONAL, f"Expected PROFESSIONAL, got {result}"

    def test_classify_domain_activity_workout_returns_health(self) -> None:
        """classify_domain should return HEALTH for workout activities."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-workout",
            label="Morning HIIT Workout",
            type="Activity",
            source="user-stated",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.HEALTH, f"Expected HEALTH, got {result}"

    def test_classify_domain_ambiguous_returns_personal(self) -> None:
        """classify_domain should return PERSONAL for ambiguous nodes."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-unknown",
            label="Something Random",
            type="Activity",
            source="user-stated",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.PERSONAL, f"Expected PERSONAL, got {result}"

    def test_classify_domain_energystate_returns_personal(self) -> None:
        """classify_domain should return PERSONAL for EnergyState nodes."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="energy-low",
            label="Low Energy",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.PERSONAL, f"Expected PERSONAL, got {result}"

    def test_classify_domain_timeslot_returns_personal(self) -> None:
        """classify_domain should return PERSONAL for TimeSlot nodes."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="timeslot-monday",
            label="Monday Morning",
            type="TimeSlot",
            source="ai-inferred",
            metadata={},
        )

        result = classify_domain(node)

        assert result == Domain.PERSONAL, f"Expected PERSONAL, got {result}"

    def test_classify_domain_person_colleague_returns_professional(self) -> None:
        """classify_domain should return PROFESSIONAL for work colleagues."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="person-steve",
            label="Steve from work",
            type="Person",
            source="user-stated",
            metadata={"context": "colleague"},
        )

        result = classify_domain(node)

        assert result == Domain.PROFESSIONAL, f"Expected PROFESSIONAL, got {result}"

    def test_classify_domain_uses_metadata_domain_if_present(self) -> None:
        """classify_domain should use domain from metadata if present."""
        from sentinel.core.rules import classify_domain
        from sentinel.core.types import Domain, Node

        node = Node(
            id="activity-ambiguous",
            label="Event",
            type="Activity",
            source="user-stated",
            metadata={"domain": "HEALTH"},
        )

        result = classify_domain(node)

        assert result == Domain.HEALTH, f"Expected HEALTH from metadata, got {result}"


class TestIsCrossDomainCollision:
    """Tests for is_cross_domain_collision function (Story 2.2)."""

    def test_is_cross_domain_collision_social_to_professional_returns_true(self) -> None:
        """Cross-domain collision from SOCIAL to PROFESSIONAL should return True."""
        from sentinel.core.rules import is_cross_domain_collision
        from sentinel.core.types import Domain

        result = is_cross_domain_collision(Domain.SOCIAL, Domain.PROFESSIONAL)

        assert result is True, f"Expected True for SOCIAL→PROFESSIONAL, got {result}"

    def test_is_cross_domain_collision_same_domain_returns_false(self) -> None:
        """Same domain collision should return False."""
        from sentinel.core.rules import is_cross_domain_collision
        from sentinel.core.types import Domain

        result = is_cross_domain_collision(Domain.PROFESSIONAL, Domain.PROFESSIONAL)

        assert result is False, f"Expected False for same domain, got {result}"

    def test_is_cross_domain_collision_personal_to_professional_returns_true(self) -> None:
        """Cross-domain collision from PERSONAL to PROFESSIONAL should return True."""
        from sentinel.core.rules import is_cross_domain_collision
        from sentinel.core.types import Domain

        result = is_cross_domain_collision(Domain.PERSONAL, Domain.PROFESSIONAL)

        assert result is True, f"Expected True for PERSONAL→PROFESSIONAL, got {result}"

    def test_is_cross_domain_collision_social_to_health_returns_true(self) -> None:
        """Cross-domain collision from SOCIAL to HEALTH should return True."""
        from sentinel.core.rules import is_cross_domain_collision
        from sentinel.core.types import Domain

        result = is_cross_domain_collision(Domain.SOCIAL, Domain.HEALTH)

        assert result is True, f"Expected True for SOCIAL→HEALTH, got {result}"

    def test_is_cross_domain_collision_health_to_health_returns_false(self) -> None:
        """Same HEALTH domain should return False."""
        from sentinel.core.rules import is_cross_domain_collision
        from sentinel.core.types import Domain

        result = is_cross_domain_collision(Domain.HEALTH, Domain.HEALTH)

        assert result is False, f"Expected False for HEALTH→HEALTH, got {result}"


class TestDetectCrossDomainCollisions:
    """Tests for detect_cross_domain_collisions function (Story 2.2)."""

    def test_detect_cross_domain_collisions_finds_social_to_professional(self) -> None:
        """Should detect collision crossing from SOCIAL to PROFESSIONAL domain."""
        from sentinel.core.rules import detect_cross_domain_collisions
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
            ),
            Node(
                id="energy-drained",
                label="drained",
                type="EnergyState",
                source="ai-inferred",
            ),
            Node(
                id="energy-focused",
                label="focused",
                type="EnergyState",
                source="ai-inferred",
            ),
            Node(
                id="activity-presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(
                source_id="person-aunt-susan",
                target_id="energy-drained",
                relationship="DRAINS",
                confidence=0.85,
            ),
            Edge(
                source_id="energy-drained",
                target_id="energy-focused",
                relationship="CONFLICTS_WITH",
                confidence=0.80,
            ),
            Edge(
                source_id="activity-presentation",
                target_id="energy-focused",
                relationship="REQUIRES",
                confidence=0.90,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        collisions = detect_cross_domain_collisions(graph)

        assert len(collisions) >= 1, f"Expected at least 1 collision, got {len(collisions)}"
        # Verify it's marked as cross-domain via enhanced path labels
        assert any("[SOCIAL]" in str(c.path) for c in collisions), (
            "Should have SOCIAL domain label in path"
        )

    def test_detect_cross_domain_collisions_empty_graph_returns_empty(self) -> None:
        """Should return empty list for empty graph."""
        from sentinel.core.rules import detect_cross_domain_collisions
        from sentinel.core.types import Graph

        graph = Graph(nodes=(), edges=())

        collisions = detect_cross_domain_collisions(graph)

        assert collisions == [], f"Expected empty list, got {collisions}"

    def test_detect_cross_domain_collisions_no_drains_returns_empty(self) -> None:
        """Should return empty list when no DRAINS edges exist."""
        from sentinel.core.rules import detect_cross_domain_collisions
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
        )
        edges = (Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),)
        graph = Graph(nodes=nodes, edges=edges)

        collisions = detect_cross_domain_collisions(graph)

        assert collisions == [], f"Expected empty list, got {collisions}"


class TestEnhancedPatternMatching:
    """Tests for enhanced collision pattern matching (Story 2.2 Task 3)."""

    def test_matches_collision_pattern_validates_edge_sequence(self) -> None:
        """Pattern should validate DRAINS → CONFLICTS_WITH → REQUIRES sequence."""
        from sentinel.core.rules import CollisionPath
        from sentinel.core.types import Edge

        # Valid sequence
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

        assert path.matches_collision_pattern() is True, "Valid sequence should match"

    def test_matches_collision_pattern_wrong_order_still_matches(self) -> None:
        """Pattern with all relations but different order should still match.

        Note: Story 2.1 pattern matching checks presence, not order.
        Order validation is handled by traversal starting from DRAINS.
        """
        from sentinel.core.rules import CollisionPath
        from sentinel.core.types import Edge

        # All relations present but different order
        edges = (
            Edge(
                source_id="activity", target_id="focused", relationship="REQUIRES", confidence=0.9
            ),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.7,
            ),
            Edge(source_id="person", target_id="drained", relationship="DRAINS", confidence=0.8),
        )
        path = CollisionPath(edges=edges)

        # matches_collision_pattern() checks presence, not strict order
        assert path.matches_collision_pattern() is True, "All relations present should match"


class TestScoreCollisionWithDomains:
    """Tests for score_collision_with_domains function (Story 2.2 Task 4)."""

    def test_score_collision_with_domains_adds_domain_labels(self) -> None:
        """Should add domain labels to path for display."""
        from sentinel.core.rules import CollisionPath, score_collision_with_domains
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="aunt", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="focused", label="focused", type="EnergyState", source="ai-inferred"),
            Node(
                id="presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(source_id="aunt", target_id="drained", relationship="DRAINS", confidence=0.8),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.7,
            ),
            Edge(
                source_id="presentation",
                target_id="focused",
                relationship="REQUIRES",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = score_collision_with_domains(path, graph)

        # First element should have SOCIAL label (source of DRAINS)
        assert "[SOCIAL]" in result.path[0], (
            f"Expected SOCIAL label in first element: {result.path}"
        )
        # PROFESSIONAL label should be on the activity that REQUIRES energy
        # This may not be the last element (which is the energy state)
        assert any("[PROFESSIONAL]" in str(label) for label in result.path), (
            f"Expected PROFESSIONAL label somewhere in path: {result.path}"
        )

    def test_score_collision_with_domains_boosts_cross_domain_confidence(self) -> None:
        """Should boost confidence for cross-domain collisions."""
        from sentinel.core.rules import (
            CollisionPath,
            score_collision,
            score_collision_with_domains,
        )
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="aunt", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="focused", label="focused", type="EnergyState", source="ai-inferred"),
            Node(
                id="presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(source_id="aunt", target_id="drained", relationship="DRAINS", confidence=0.8),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.7,
            ),
            Edge(
                source_id="presentation",
                target_id="focused",
                relationship="REQUIRES",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        base_result = score_collision(path, graph)
        enhanced_result = score_collision_with_domains(path, graph)

        # Cross-domain should have higher confidence (10% boost)
        assert enhanced_result.confidence > base_result.confidence, (
            f"Cross-domain {enhanced_result.confidence} should exceed base {base_result.confidence}"
        )

    def test_score_collision_with_domains_preserves_source_breakdown(self) -> None:
        """Should preserve source breakdown from base scoring."""
        from sentinel.core.rules import CollisionPath, score_collision_with_domains
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="aunt", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="focused", label="focused", type="EnergyState", source="ai-inferred"),
            Node(
                id="presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(source_id="aunt", target_id="drained", relationship="DRAINS", confidence=0.8),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.7,
            ),
            Edge(
                source_id="presentation",
                target_id="focused",
                relationship="REQUIRES",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = score_collision_with_domains(path, graph)

        assert "ai_inferred" in result.source_breakdown, "Should have ai_inferred count"
        assert "user_stated" in result.source_breakdown, "Should have user_stated count"


class TestIsValidCollision:
    """Tests for is_valid_collision function (Story 2.2 Task 5)."""

    def test_is_valid_collision_returns_true_for_valid_path(self) -> None:
        """Should return True for valid collision path."""
        from sentinel.core.rules import CollisionPath, is_valid_collision
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="person", label="Aunt", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="focused", label="focused", type="EnergyState", source="ai-inferred"),
            Node(id="activity", label="Presentation", type="Activity", source="user-stated"),
        )
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
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = is_valid_collision(path, graph)

        assert result is True, f"Expected True for valid path, got {result}"

    def test_is_valid_collision_returns_false_for_short_path(self) -> None:
        """Should return False for path with fewer than 3 edges."""
        from sentinel.core.rules import CollisionPath, is_valid_collision
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="a", relationship="CONFLICTS_WITH", confidence=0.7),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = is_valid_collision(path, graph)

        assert result is False, f"Expected False for short path, got {result}"

    def test_is_valid_collision_returns_false_for_missing_pattern(self) -> None:
        """Should return False for path missing collision pattern."""
        from sentinel.core.rules import CollisionPath, is_valid_collision
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="a", label="A", type="Activity", source="user-stated"),
            Node(id="b", label="B", type="Activity", source="user-stated"),
            Node(id="c", label="C", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(source_id="a", target_id="b", relationship="INVOLVES", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="SCHEDULED_AT", confidence=0.7),
            Edge(source_id="c", target_id="a", relationship="BELONGS_TO", confidence=0.9),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = is_valid_collision(path, graph)

        assert result is False, f"Expected False for missing pattern, got {result}"

    def test_is_valid_collision_returns_false_for_same_start_end(self) -> None:
        """Should return False for self-loop (same start and end node)."""
        from sentinel.core.rules import CollisionPath, is_valid_collision
        from sentinel.core.types import Edge, Graph, Node

        nodes = (
            Node(id="a", label="A", type="Person", source="user-stated"),
            Node(id="b", label="B", type="EnergyState", source="ai-inferred"),
            Node(id="c", label="C", type="EnergyState", source="ai-inferred"),
        )
        # Path that loops back: a -> b -> c -> a
        edges = (
            Edge(source_id="a", target_id="b", relationship="DRAINS", confidence=0.8),
            Edge(source_id="b", target_id="c", relationship="CONFLICTS_WITH", confidence=0.7),
            Edge(source_id="c", target_id="a", relationship="REQUIRES", confidence=0.9),
        )
        graph = Graph(nodes=nodes, edges=edges)
        path = CollisionPath(edges=edges)

        result = is_valid_collision(path, graph)

        assert result is False, f"Expected False for self-loop, got {result}"


class TestDeduplicateCollisions:
    """Tests for collision deduplication (Story 2.2 Task 5)."""

    def test_deduplicate_collisions_removes_duplicates(self) -> None:
        """Should remove duplicate collision paths."""
        from sentinel.core.rules import deduplicate_collisions
        from sentinel.core.types import ScoredCollision

        collisions = [
            ScoredCollision(path=("A", "DRAINS", "B"), confidence=0.8, source_breakdown={}),
            ScoredCollision(path=("A", "DRAINS", "B"), confidence=0.8, source_breakdown={}),
            ScoredCollision(path=("C", "DRAINS", "D"), confidence=0.7, source_breakdown={}),
        ]

        result = deduplicate_collisions(collisions)

        assert len(result) == 2, f"Expected 2 unique collisions, got {len(result)}"

    def test_deduplicate_collisions_preserves_higher_confidence(self) -> None:
        """Should keep collision with higher confidence when deduplicating."""
        from sentinel.core.rules import deduplicate_collisions
        from sentinel.core.types import ScoredCollision

        collisions = [
            ScoredCollision(path=("A", "DRAINS", "B"), confidence=0.6, source_breakdown={}),
            ScoredCollision(path=("A", "DRAINS", "B"), confidence=0.9, source_breakdown={}),
        ]

        result = deduplicate_collisions(collisions)

        assert len(result) == 1, f"Expected 1 collision, got {len(result)}"
        assert result[0].confidence == 0.9, (
            f"Expected highest confidence 0.9, got {result[0].confidence}"
        )

    def test_deduplicate_collisions_empty_input_returns_empty(self) -> None:
        """Should return empty list for empty input (edge case)."""
        from sentinel.core.rules import deduplicate_collisions

        result = deduplicate_collisions([])

        assert result == [], f"Expected empty list, got {result}"


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
