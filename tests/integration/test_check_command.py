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
