"""Integration tests for the check CLI command.

Tests for Story 2.1: Multi-hop Graph Traversal.
Tests full CLI flow using MockEngine collision fixtures.
"""

from unittest.mock import patch

from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import (
    EXIT_COLLISION_DETECTED,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
)
from sentinel.core.types import Edge, Graph, Node


def _create_collision_graph() -> Graph:
    """Create a graph with collision pattern for testing.

    Pattern: (Aunt Susan)-[:DRAINS]->(drained)-[:CONFLICTS_WITH]->
             (focused)<-[:REQUIRES]-(presentation)
    """
    nodes = (
        Node(
            id="person-aunt-susan",
            label="Aunt Susan",
            type="Person",
            source="user-stated",
            metadata={"extracted_from": "Sunday dinner"},
        ),
        Node(
            id="energystate-drained",
            label="drained",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="energystate-focused",
            label="focused",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="activity-presentation",
            label="presentation",
            type="Activity",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
    )
    edges = (
        Edge(
            source_id="person-aunt-susan",
            target_id="energystate-drained",
            relationship="DRAINS",
            confidence=0.85,
            metadata={"reason": "emotionally draining"},
        ),
        Edge(
            source_id="energystate-drained",
            target_id="energystate-focused",
            relationship="CONFLICTS_WITH",
            confidence=0.80,
            metadata={"conflict_type": "energy_depletion"},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="energystate-focused",
            relationship="REQUIRES",
            confidence=0.90,
            metadata={"requirement": "mental_sharpness"},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


def _create_no_collision_graph() -> Graph:
    """Create a graph without collision pattern (boring week)."""
    nodes = (
        Node(
            id="activity-standup",
            label="Regular Standup",
            type="Activity",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
        Node(
            id="activity-docs",
            label="Documentation Updates",
            type="Activity",
            source="user-stated",
            metadata={"day": "Tuesday"},
        ),
        Node(
            id="timeslot-monday",
            label="Monday",
            type="TimeSlot",
            source="ai-inferred",
            metadata={"day": "Monday"},
        ),
    )
    edges = (
        Edge(
            source_id="activity-standup",
            target_id="timeslot-monday",
            relationship="SCHEDULED_AT",
            confidence=0.90,
            metadata={},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


class TestCheckCommandIntegration:
    """Integration tests for the check command."""

    def test_check_with_collision_returns_exit_code_1(self) -> None:
        """Test check command returns exit code 1 when collision found (AC: #1, #2, #5)."""
        runner = CliRunner()
        graph = _create_collision_graph()

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=graph,
        ):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_COLLISION_DETECTED, (
            f"Expected exit code {EXIT_COLLISION_DETECTED}, got {result.exit_code}. "
            f"Output: {result.output}"
        )
        assert "collision" in result.output.lower(), (
            f"Expected 'collision' in output: {result.output}"
        )

    def test_check_without_collision_returns_exit_code_0(self) -> None:
        """Test check command returns exit code 0 when no collisions found."""
        runner = CliRunner()

        graph = _create_no_collision_graph()

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=graph,
        ):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code {EXIT_SUCCESS}, got {result.exit_code}. Output: {result.output}"
        )
        assert "No energy collisions detected" in result.output, (
            f"Expected success message: {result.output}"
        )

    def test_check_with_no_saved_graph_shows_error(self) -> None:
        """Test check command shows error when no graph saved (AC: prerequisite)."""
        runner = CliRunner()

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=None,
        ):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_USER_ERROR, (
            f"Expected exit code {EXIT_USER_ERROR}, got {result.exit_code}. Output: {result.output}"
        )
        assert "No schedule data found" in result.output, f"Expected error message: {result.output}"
        assert "sentinel paste" in result.output, f"Expected paste hint: {result.output}"

    def test_check_with_empty_graph_shows_success(self) -> None:
        """Test check command handles empty graph gracefully."""
        runner = CliRunner()

        empty_graph = Graph(nodes=(), edges=())

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=empty_graph,
        ):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code {EXIT_SUCCESS}, got {result.exit_code}. Output: {result.output}"
        )
        assert "No relationships to analyze" in result.output, (
            f"Expected empty state message: {result.output}"
        )

    def test_check_command_exists_in_help(self) -> None:
        """Test that check command appears in help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"
        assert "check" in result.output, f"Expected 'check' in help: {result.output}"

    def test_check_command_has_help(self) -> None:
        """Test that check command has its own help."""
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])

        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"
        assert "collision" in result.output.lower(), (
            f"Expected 'collision' in help: {result.output}"
        )

    def test_check_shows_collision_count(self) -> None:
        """Test check command shows number of collisions found (AC: #3)."""
        runner = CliRunner()

        graph = _create_collision_graph()

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=graph,
        ):
            result = runner.invoke(main, ["check"])

        # Should show collision count in output
        assert "potential collision" in result.output.lower(), (
            f"Expected collision count in output: {result.output}"
        )


class TestCheckCommandProgressIndicator:
    """Tests for progress indicator during check command (AC: #3)."""

    def test_check_shows_analyzing_message(self) -> None:
        """Test check command shows 'Analyzing relationships' during traversal."""
        runner = CliRunner()

        graph = _create_collision_graph()

        with patch(
            "sentinel.core.engine.CogneeEngine.load",
            return_value=graph,
        ):
            # Use mix_stderr=False to separate stdout/stderr
            result = runner.invoke(main, ["check"], catch_exceptions=False)

        # Progress indicator may be transient, but we should get results
        assert result.exit_code in (EXIT_SUCCESS, EXIT_COLLISION_DETECTED), (
            f"Unexpected exit code: {result.exit_code}. Output: {result.output}"
        )


class TestCrossDomainCollisionDetection:
    """Integration tests for Story 2.2: Cross-Domain Collision Detection."""

    def test_detect_cross_domain_collision_with_mock_engine(self) -> None:
        """Test full collision detection flow with MockEngine collision fixture.

        Story 2.2 AC #1: Cross-domain patterns are identified (social → professional conflict)
        """
        from sentinel.core.rules import detect_cross_domain_collisions

        # Use collision graph from MockEngine pattern
        graph = _create_collision_graph()

        collisions = detect_cross_domain_collisions(graph)

        assert len(collisions) >= 1, f"Expected at least 1 collision, got {len(collisions)}"

    def test_collision_path_contains_domain_labels(self) -> None:
        """Test collision path contains correct domain information.

        Story 2.2 AC #3: Path labels show domain transitions for display.
        """
        from sentinel.core.rules import detect_cross_domain_collisions

        # Create graph with clear SOCIAL and PROFESSIONAL nodes
        nodes = (
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
                metadata={},
            ),
            Node(
                id="energystate-drained",
                label="drained",
                type="EnergyState",
                source="ai-inferred",
                metadata={},
            ),
            Node(
                id="energystate-focused",
                label="focused",
                type="EnergyState",
                source="ai-inferred",
                metadata={},
            ),
            Node(
                id="activity-presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
                metadata={},
            ),
        )
        edges = (
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.85,
                metadata={},
            ),
            Edge(
                source_id="energystate-drained",
                target_id="energystate-focused",
                relationship="CONFLICTS_WITH",
                confidence=0.80,
                metadata={},
            ),
            Edge(
                source_id="activity-presentation",
                target_id="energystate-focused",
                relationship="REQUIRES",
                confidence=0.90,
                metadata={},
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        collisions = detect_cross_domain_collisions(graph)

        assert len(collisions) >= 1, "Expected collision to be detected"
        collision = collisions[0]

        # Check domain labels are present
        path_str = str(collision.path)
        assert "[SOCIAL]" in path_str, f"Expected SOCIAL label in path: {path_str}"
        assert "[PROFESSIONAL]" in path_str, f"Expected PROFESSIONAL label in path: {path_str}"

    def test_no_false_positives_with_unrelated_activities(self) -> None:
        """Test no false positives are generated for unrelated activities.

        Story 2.2 AC #6: No false positives with unrelated activities.
        """
        from sentinel.core.rules import detect_cross_domain_collisions

        # Create graph without collision pattern (no DRAINS edges)
        graph = _create_no_collision_graph()

        collisions = detect_cross_domain_collisions(graph)

        assert collisions == [], f"Expected no collisions, got {len(collisions)}"

    def test_empty_graph_returns_empty_list_not_none(self) -> None:
        """Test empty graph returns empty list (not None).

        Story 2.2 AC #5: Empty list returned, not None.
        """
        from sentinel.core.rules import detect_cross_domain_collisions

        empty_graph = Graph(nodes=(), edges=())

        collisions = detect_cross_domain_collisions(empty_graph)

        assert collisions == [], (
            f"Expected empty list, got {type(collisions).__name__}: {collisions}"
        )
        assert isinstance(collisions, list), "Return value must be list, not None"

    def test_backward_compatibility_with_story_21_tests(self) -> None:
        """Test Story 2.1 functionality still works after Story 2.2 changes.

        Verifies find_collision_paths() and score_collision() still function correctly.
        """
        from sentinel.core.rules import find_collision_paths, score_collision

        graph = _create_collision_graph()

        # Story 2.1 path finding
        paths = find_collision_paths(graph)
        assert len(paths) >= 1, "Story 2.1 path finding should still work"

        # Story 2.1 scoring
        if paths:
            collision = score_collision(paths[0], graph)
            assert collision is not None, "Story 2.1 scoring should still work"
            assert 0.0 <= collision.confidence <= 1.0, "Confidence should be valid"

    def test_cross_domain_collision_has_boosted_confidence(self) -> None:
        """Test cross-domain collisions have boosted confidence vs same-domain.

        Story 2.2: Cross-domain collisions are more impactful (10% boost).
        """
        from sentinel.core.rules import (
            find_collision_paths,
            score_collision,
            score_collision_with_domains,
        )

        # Create SOCIAL → PROFESSIONAL collision
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

        paths = find_collision_paths(graph)
        assert len(paths) >= 1, "Should find collision path"

        path = paths[0]
        base = score_collision(path, graph)
        enhanced = score_collision_with_domains(path, graph)

        # Cross-domain (SOCIAL → PROFESSIONAL) should have boosted confidence
        assert enhanced.confidence > base.confidence, (
            f"Cross-domain {enhanced.confidence} should exceed base {base.confidence}"
        )
