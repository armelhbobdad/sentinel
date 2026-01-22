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
        assert "Did you mean" in result.output, f"Should show suggestions. Output:\n{result.output}"

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
    """Tests for --depth option (preparation for Story 4-2)."""

    def test_graph_accepts_depth_option(self, sample_graph: Graph) -> None:
        """sentinel graph --depth option is accepted."""
        runner = CliRunner()

        with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.load.return_value = sample_graph

            result = runner.invoke(main, ["graph", "Aunt Susan", "--depth", "1"])

        # Should accept the option without error (full depth control in Story 4-2)
        assert result.exit_code == EXIT_SUCCESS, f"Output: {result.output}"

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


class TestGraphCommandIntegration:
    """Integration tests for graph command with persistence."""

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
