"""Tests for the graph CLI command.

Tests the `sentinel graph` command for exploring the knowledge graph.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_SUCCESS, EXIT_USER_ERROR
from sentinel.core.types import Edge, Graph, Node


@pytest.fixture
def sample_graph() -> Graph:
    """Create a sample graph for testing graph exploration."""
    nodes = (
        Node(id="1", label="Aunt Susan", type="Person", source="user-stated"),
        Node(id="2", label="Dinner", type="Activity", source="user-stated"),
        Node(id="3", label="Drained", type="EnergyState", source="ai-inferred"),
        Node(id="4", label="Strategy Presentation", type="Activity", source="user-stated"),
        Node(id="5", label="High Focus", type="EnergyState", source="ai-inferred"),
    )
    edges = (
        Edge(source_id="1", target_id="3", relationship="DRAINS", confidence=0.9),
        Edge(source_id="2", target_id="1", relationship="INVOLVES", confidence=0.8),
        Edge(source_id="4", target_id="5", relationship="REQUIRES", confidence=0.85),
        Edge(source_id="3", target_id="5", relationship="CONFLICTS_WITH", confidence=0.7),
    )
    return Graph(nodes=nodes, edges=edges)


class TestGraphCommandNoArg:
    """Tests for `sentinel graph` without a node argument."""

    def test_graph_no_arg_shows_full_graph(self, sample_graph: Graph, tmp_path: Path) -> None:
        """sentinel graph with no arguments shows full graph."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph"])

        assert result.exit_code == EXIT_SUCCESS, f"Exit {result.exit_code}: {result.output}"
        assert "Aunt Susan" in result.output
        assert "Dinner" in result.output

    def test_graph_no_arg_no_graph_shows_error(self, tmp_path: Path) -> None:
        """sentinel graph with no stored graph shows error."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = None

            result = runner.invoke(main, ["graph"])

        assert result.exit_code == EXIT_USER_ERROR
        assert "No graph found" in result.output or "paste" in result.output.lower()


class TestGraphCommandWithNode:
    """Tests for `sentinel graph <node>` with a node argument."""

    def test_graph_with_valid_node_shows_neighborhood(self, sample_graph: Graph) -> None:
        """sentinel graph 'Aunt Susan' shows neighborhood around node."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Focal node MUST be highlighted with "*" prefix (AC#2)
        assert "* [Aunt Susan]" in result.output, (
            f"Focal node not highlighted with '* [Aunt Susan]'. Output:\n{result.output}"
        )

    def test_graph_with_fuzzy_match_finds_node(self, sample_graph: Graph) -> None:
        """sentinel graph 'Aun Susan' fuzzy matches 'Aunt Susan'."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            # Use a query close enough to match (e.g., typo in name)
            result = runner.invoke(main, ["graph", "Aunt Susa"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Should show fuzzy match notice
        assert "Matched:" in result.output or "Aunt Susan" in result.output

    def test_graph_node_not_found_shows_error(self, sample_graph: Graph) -> None:
        """sentinel graph 'Unknown Person' shows error with suggestions."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Unknown Person"])

        assert result.exit_code == EXIT_USER_ERROR, f"Expected exit code 1, got {result.exit_code}"
        assert "not found" in result.output.lower(), "Error message should say 'not found'"
        # AC#4: Should show suggestions when node not found
        assert "Did you mean" in result.output, (
            f"Should show 'Did you mean' suggestions. Output:\n{result.output}"
        )

    def test_graph_shows_relationship_types(self, sample_graph: Graph) -> None:
        """Graph display shows relationship types on edges."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan"])

        assert result.exit_code == EXIT_SUCCESS
        # Should show relationship types
        assert "DRAINS" in result.output or "INVOLVES" in result.output


class TestGraphCommandHelpText:
    """Tests for graph command help text."""

    def test_graph_help_shows_usage(self) -> None:
        """sentinel graph --help shows usage examples."""
        runner = CliRunner()

        result = runner.invoke(main, ["graph", "--help"])

        assert result.exit_code == 0
        assert "graph" in result.output.lower()
        # Should have examples
        assert "sentinel graph" in result.output


class TestGraphCommandDepthOption:
    """Tests for --depth option (Story 4-2: Depth Control for Exploration)."""

    def test_graph_depth_1_shows_only_direct_connections(self, sample_graph: Graph) -> None:
        """sentinel graph --depth 1 shows only directly connected nodes (AC#1)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "1"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Direct connections from Aunt Susan: Drained (via DRAINS), Dinner (via INVOLVES)
        # NOT direct: Strategy Presentation, High Focus (2+ hops away)
        assert "Drained" in result.output, "Direct connection 'Drained' should appear"
        assert "Strategy Presentation" not in result.output, (
            f"Depth 1 should NOT show 'Strategy Presentation' (2+ hops). Output:\n{result.output}"
        )
        assert "High Focus" not in result.output, (
            f"Depth 1 should NOT show 'High Focus' (2+ hops). Output:\n{result.output}"
        )

    def test_graph_depth_0_shows_only_focal_node(self, sample_graph: Graph) -> None:
        """sentinel graph --depth 0 shows only the focal node."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "0"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Summary should show 1 node, 0 relationships
        assert "1 nodes" in result.output, f"Expected 1 node at depth 0. Output:\n{result.output}"
        assert "0 relationships" in result.output, (
            f"Expected 0 relationships at depth 0. Output:\n{result.output}"
        )

    def test_graph_default_depth_is_2(self, sample_graph: Graph) -> None:
        """Default depth is 2 when not specified (AC#3)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Summary should mention depth 2
        assert "depth 2" in result.output.lower(), (
            f"Expected 'depth 2' in output. Output:\n{result.output}"
        )

    def test_graph_negative_depth_shows_error(self, sample_graph: Graph) -> None:
        """Negative depth shows error (AC#5 edge case)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "-1"])

        assert result.exit_code == EXIT_USER_ERROR, f"Expected exit 1. Output: {result.output}"
        assert "non-negative" in result.output.lower() or "error" in result.output.lower(), (
            f"Expected error message about non-negative depth. Output:\n{result.output}"
        )

    def test_graph_depth_exceeds_max_shows_warning_and_clamps(self, sample_graph: Graph) -> None:
        """Depth > 5 shows warning and clamps to 5 (AC#4)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "10"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Must show warning about maximum depth
        assert "Maximum depth is 5" in result.output, (
            f"Expected 'Maximum depth is 5' warning. Output:\n{result.output}"
        )
        # Summary should show depth 5 (clamped)
        assert "depth 5" in result.output.lower(), (
            f"Expected 'depth 5' in summary (clamped). Output:\n{result.output}"
        )

    @pytest.mark.parametrize("depth", [1, 2, 3, 4, 5])
    def test_graph_valid_depths_succeed_without_warning(
        self, sample_graph: Graph, depth: int
    ) -> None:
        """All valid depths (1-5) work without clamping warning."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", str(depth)])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # No clamping warning for valid depths
        assert "Maximum depth" not in result.output, (
            f"Should not show clamping warning for depth {depth}. Output:\n{result.output}"
        )

    def test_graph_help_text_shows_depth_max(self) -> None:
        """Help text mentions max depth limit (AC#4)."""
        runner = CliRunner()

        result = runner.invoke(main, ["graph", "--help"])

        assert result.exit_code == 0
        # Help should mention the max limit explicitly
        assert "max: 5" in result.output.lower(), (
            f"Help text should mention 'max: 5'. Output:\n{result.output}"
        )

    def test_graph_depth_3_shows_extended_connections(self, sample_graph: Graph) -> None:
        """Depth 3 shows nodes up to 3 hops away (AC#2)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "3"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Should show depth 3 in summary
        assert "depth 3" in result.output.lower(), (
            f"Expected 'depth 3' in output. Output:\n{result.output}"
        )
        # With depth 3 from Aunt Susan, should reach extended connections:
        # Aunt Susan -> Drained (depth 1) -> High Focus (depth 2)
        # Both MUST be visible at depth 3
        assert "Drained" in result.output, (
            f"Expected 'Drained' (depth 1) at depth 3. Output:\n{result.output}"
        )
        assert "High Focus" in result.output, (
            f"Expected 'High Focus' (depth 2) at depth 3. Output:\n{result.output}"
        )


class TestGraphCommandLargeGraphWarning:
    """Tests for large graph warning (Story 4-2 AC#6)."""

    @pytest.fixture
    def large_graph(self) -> Graph:
        """Create a graph with more than 50 nodes for large graph testing."""
        nodes = tuple(
            Node(id=str(i), label=f"Node{i}", type="Entity", source="user-stated")
            for i in range(60)  # 60 nodes to exceed threshold of 50
        )
        # Create a star topology from node 0 to all others
        edges = tuple(
            Edge(source_id="0", target_id=str(i), relationship="CONNECTS", confidence=0.9)
            for i in range(1, 60)
        )
        return Graph(nodes=nodes, edges=edges)

    def test_graph_large_result_shows_warning(self, large_graph: Graph) -> None:
        """Large graph results (>50 nodes) show warning (AC#6)."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = large_graph

            result = runner.invoke(main, ["graph", "Node0", "--depth", "5"])

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        # Should show warning about large graph with node count
        assert "Large graph" in result.output, (
            f"Expected 'Large graph' warning. Output:\n{result.output}"
        )
        assert "60 nodes" in result.output, (
            f"Expected node count in warning. Output:\n{result.output}"
        )
        # Should mention using lower depth for cleaner output
        assert "Use lower --depth" in result.output, (
            f"Expected 'Use lower --depth' guidance. Output:\n{result.output}"
        )

    def test_graph_under_threshold_no_warning(self, sample_graph: Graph) -> None:
        """Graph under 50 nodes does not show large graph warning."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph  # 5 nodes

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "2"])

        assert result.exit_code == EXIT_SUCCESS
        # Should NOT show "Use lower" warning for small graphs
        assert "Use lower" not in result.output, (
            f"Should not show large graph warning for small graph. Output:\n{result.output}"
        )

    def test_graph_depth_5_performance(self, large_graph: Graph) -> None:
        """Depth 5 completes within NFR4 (3 seconds) (AC: Task 4.8)."""
        import time

        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = large_graph

            start = time.time()
            result = runner.invoke(main, ["graph", "Node0", "--depth", "5"])
            elapsed = time.time() - start

        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"
        assert elapsed < 3.0, f"Depth 5 took {elapsed:.2f}s, expected < 3s (NFR4)"


class TestGraphCommandSubsetBehavior:
    """Tests for graph neighborhood subset behavior."""

    def test_graph_shows_subset_of_full_graph(self, sample_graph: Graph) -> None:
        """Graph neighborhood contains subset of nodes from full graph."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            # Full graph has 5 nodes
            full_result = runner.invoke(main, ["graph"])
            assert full_result.exit_code == EXIT_SUCCESS

            # Neighborhood should have fewer nodes (depth 2 from Aunt Susan)
            neighborhood_result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "1"])
            assert neighborhood_result.exit_code == EXIT_SUCCESS

            # Verify neighborhood is a subset - check summary line
            assert "Showing" in neighborhood_result.output
            # Strategy Presentation is not connected to Aunt Susan, should not appear
            assert "Strategy Presentation" not in neighborhood_result.output
