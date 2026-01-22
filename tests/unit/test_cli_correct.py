"""Unit tests for sentinel correct CLI command (Story 3.1 Task 4).

Tests the correct command for deleting AI-inferred nodes and listing corrections.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sentinel.core.types import Edge, Graph, Node


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def graph_with_ai_nodes(tmp_path: Path) -> Graph:
    """Create a graph with both user-stated and AI-inferred nodes."""
    return Graph(
        nodes=(
            Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
            Node(
                id="activity-dinner",
                label="Dinner with Aunt Susan",
                type="Activity",
                source="user-stated",
            ),
            Node(
                id="energystate-drained", label="Drained", type="EnergyState", source="ai-inferred"
            ),
            Node(id="energystate-tired", label="Tired", type="EnergyState", source="ai-inferred"),
            Node(
                id="energystate-focused", label="Focused", type="EnergyState", source="ai-inferred"
            ),
        ),
        edges=(
            Edge(
                source_id="activity-dinner",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.9,
            ),
            Edge(
                source_id="energystate-drained",
                target_id="energystate-focused",
                relationship="CONFLICTS_WITH",
                confidence=0.8,
            ),
        ),
    )


def setup_graph_file(tmp_path: Path, graph: Graph) -> None:
    """Setup a graph.db file for testing."""
    from sentinel.core.engine import CogneeEngine

    sentinel_dir = tmp_path / "sentinel"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
        engine = CogneeEngine()
        engine.persist(graph)


class TestCorrectDeleteCommand:
    """Tests for `sentinel correct delete` command (AC: #1, #7, #8)."""

    def test_correct_delete_removes_ai_inferred_node(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete removes AI-inferred node and shows confirmation (AC: #1)."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "delete", "Drained", "--yes"])

        assert result.exit_code == 0, f"Should succeed, got: {result.output}"
        assert "Drained" in result.output, f"Should confirm deletion: {result.output}"
        assert "deleted" in result.output.lower(), f"Should confirm deletion: {result.output}"

    def test_correct_delete_shows_fuzzy_suggestions(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete shows fuzzy suggestions when no exact match (AC: #7)."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "delete", "Drainned"])

        # Should show "Did you mean" with suggestions
        assert "did you mean" in result.output.lower() or "Drained" in result.output, (
            f"Should suggest Drained: {result.output}"
        )

    def test_correct_delete_refuses_user_stated(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete refuses to delete user-stated nodes (AC: #2)."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        # "Maya" is a user-stated node label
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "delete", "Maya", "--yes"])

        # Should either not find it (ai-inferred only) or refuse
        assert (
            result.exit_code != 0
            or "user-stated" in result.output.lower()
            or "not found" in result.output.lower()
        ), f"Should refuse user-stated deletion: {result.output}"

    def test_correct_delete_prompts_for_confirmation(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete prompts for confirmation without --yes flag."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Respond 'n' to confirmation prompt
            result = runner.invoke(main, ["correct", "delete", "Drained"], input="n\n")

        # Should not delete when user says no
        assert (
            "abort" in result.output.lower()
            or "cancel" in result.output.lower()
            or result.exit_code != 0
        ), f"Should abort on 'n': {result.output}"


class TestCorrectListCommand:
    """Tests for `sentinel correct list` command (AC: #6)."""

    def test_correct_list_shows_empty_state(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct list shows message when no corrections exist (AC: #6)."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "list"])

        assert result.exit_code == 0, f"Should succeed: {result.output}"
        assert (
            "no corrections" in result.output.lower()
            or "empty" in result.output.lower()
            or "none" in result.output.lower()
        ), f"Should show empty state: {result.output}"

    def test_correct_list_shows_corrections(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct list shows existing corrections (AC: #6)."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore
        from sentinel.core.types import Correction

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        # Add a correction
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            store = CorrectionStore()
            store.add_correction(
                Correction(node_id="energystate-drained", action="delete"), reason="Test reason"
            )

            result = runner.invoke(main, ["correct", "list"])

        assert result.exit_code == 0, f"Should succeed: {result.output}"
        assert "energystate-drained" in result.output or "Drained" in result.output, (
            f"Should show correction: {result.output}"
        )


class TestCorrectCommandNoGraph:
    """Tests for correct command when no graph exists."""

    def test_correct_delete_without_graph(self, runner: CliRunner, tmp_path: Path) -> None:
        """correct delete shows error when no graph exists."""
        from sentinel.cli.commands import main

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "delete", "Drained", "--yes"])

        assert (
            result.exit_code != 0
            or "no schedule" in result.output.lower()
            or "paste" in result.output.lower()
        ), f"Should show no graph error: {result.output}"


class TestCorrectDeleteEdgeCases:
    """Tests for edge cases in correct delete."""

    def test_correct_delete_cascades_edges(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete cascades removal of connected edges (AC: #3)."""
        from sentinel.cli.commands import main
        from sentinel.core.engine import CogneeEngine

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Delete a node that has edges
            result = runner.invoke(main, ["correct", "delete", "Drained", "--yes"])

            assert result.exit_code == 0, f"Should succeed: {result.output}"

            # Verify edges were removed
            engine = CogneeEngine()
            graph = engine.load()

        # Edges referencing "energystate-drained" should be gone
        assert graph is not None, "Expected graph to be loaded"
        for edge in graph.edges:
            assert edge.source_id != "energystate-drained", f"Source edge should be removed: {edge}"
            assert edge.target_id != "energystate-drained", f"Target edge should be removed: {edge}"

    def test_correct_delete_persists_immediately(
        self, runner: CliRunner, tmp_path: Path, graph_with_ai_nodes: Graph
    ) -> None:
        """correct delete persists correction immediately (AC: #4)."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore

        setup_graph_file(tmp_path, graph_with_ai_nodes)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(main, ["correct", "delete", "Drained", "--yes"])

            assert result.exit_code == 0, f"Should succeed: {result.output}"

            # Verify correction was persisted
            store = CorrectionStore()
            corrections = store.load()

        deleted_ids = {c.node_id for c in corrections if c.action == "delete"}
        assert "energystate-drained" in deleted_ids, (
            f"Correction should be persisted: {corrections}"
        )


# Story 3-2: Edge correction CLI tests


@pytest.fixture
def graph_with_edge_for_modify(tmp_path: Path) -> Graph:
    """Create a graph with edge suitable for modification tests."""
    return Graph(
        nodes=(
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
            ),
            Node(
                id="energystate-drained",
                label="drained",
                type="EnergyState",
                source="ai-inferred",
            ),
            Node(
                id="energystate-happy",
                label="happy",
                type="EnergyState",
                source="ai-inferred",
            ),
        ),
        edges=(
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.8,
            ),
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-happy",
                relationship="CAUSES",
                confidence=0.7,
            ),
        ),
    )


class TestCorrectModifyCommand:
    """Tests for `sentinel correct modify` command (Story 3-2 Task 5)."""

    def test_correct_modify_changes_relationship(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct modify changes edge relationship type."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(
                main,
                [
                    "correct",
                    "modify",
                    "Aunt Susan",
                    "--target",
                    "drained",
                    "--relationship",
                    "ENERGIZES",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Should succeed, got: {result.output}"
        assert "ENERGIZES" in result.output or "modified" in result.output.lower(), (
            f"Should confirm modification: {result.output}"
        )

    def test_correct_modify_fuzzy_match_source(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct modify uses fuzzy matching for source node."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Typo in "Aunt Susan"
            result = runner.invoke(
                main,
                [
                    "correct",
                    "modify",
                    "Autn Susan",
                    "--target",
                    "drained",
                    "--relationship",
                    "ENERGIZES",
                ],
            )

        # Should suggest "Aunt Susan"
        assert "Aunt Susan" in result.output or "did you mean" in result.output.lower(), (
            f"Should suggest correct match: {result.output}"
        )

    def test_correct_modify_validates_relationship_type(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct modify rejects invalid relationship types."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(
                main,
                [
                    "correct",
                    "modify",
                    "Aunt Susan",
                    "--target",
                    "drained",
                    "--relationship",
                    "INVALID_TYPE",
                    "--yes",
                ],
            )

        assert result.exit_code != 0, f"Should fail for invalid type: {result.output}"
        assert "invalid" in result.output.lower(), f"Should mention invalid: {result.output}"

    def test_correct_modify_persists_correction(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct modify persists correction immediately."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(
                main,
                [
                    "correct",
                    "modify",
                    "Aunt Susan",
                    "--target",
                    "drained",
                    "--relationship",
                    "ENERGIZES",
                    "--yes",
                ],
            )

            assert result.exit_code == 0, f"Should succeed: {result.output}"

            # Verify correction was persisted
            store = CorrectionStore()
            corrections = store.load()

        modify_corrections = [c for c in corrections if c.action == "modify_relationship"]
        assert len(modify_corrections) == 1, f"Should have 1 modify correction: {corrections}"
        assert modify_corrections[0].new_value == "ENERGIZES", (
            f"Should persist ENERGIZES: {modify_corrections[0]}"
        )


class TestCorrectRemoveEdgeCommand:
    """Tests for `sentinel correct remove-edge` command (Story 3-2 Task 6)."""

    def test_correct_remove_edge_removes_edge(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct remove-edge removes edge but keeps nodes."""
        from sentinel.cli.commands import main
        from sentinel.core.engine import CogneeEngine

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(
                main,
                [
                    "correct",
                    "remove-edge",
                    "Aunt Susan",
                    "--target",
                    "drained",
                    "--yes",
                ],
            )

            assert result.exit_code == 0, f"Should succeed, got: {result.output}"
            assert "removed" in result.output.lower(), f"Should confirm removal: {result.output}"

            # Verify nodes are preserved but edge is gone
            engine = CogneeEngine()
            graph = engine.load()

        assert graph is not None, "Expected graph to be loaded"
        assert len(graph.nodes) == 3, f"Should preserve all nodes: {graph.nodes}"
        # Should only have 1 edge left (the one to happy)
        assert len(graph.edges) == 1, f"Should have removed one edge: {graph.edges}"
        assert graph.edges[0].target_id == "energystate-happy", (
            f"Should preserve other edge: {graph.edges[0]}"
        )

    def test_correct_remove_edge_fuzzy_match(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct remove-edge uses fuzzy matching for nodes."""
        from sentinel.cli.commands import main

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Typo in both labels
            result = runner.invoke(
                main,
                [
                    "correct",
                    "remove-edge",
                    "Autn Susan",
                    "--target",
                    "drainned",
                ],
            )

        # Should suggest the correct matches
        assert "Aunt Susan" in result.output or "drained" in result.output, (
            f"Should suggest matches: {result.output}"
        )

    def test_correct_remove_edge_persists_correction(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct remove-edge persists correction immediately."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = runner.invoke(
                main,
                [
                    "correct",
                    "remove-edge",
                    "Aunt Susan",
                    "--target",
                    "drained",
                    "--yes",
                ],
            )

            assert result.exit_code == 0, f"Should succeed: {result.output}"

            # Verify correction was persisted
            store = CorrectionStore()
            corrections = store.load()

        remove_corrections = [c for c in corrections if c.action == "remove_edge"]
        assert len(remove_corrections) == 1, f"Should have 1 remove_edge correction: {corrections}"


class TestCorrectListEdgeCorrections:
    """Tests for correct list showing edge corrections (Story 3-2 Task 7)."""

    def test_correct_list_shows_edge_modifications(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct list displays edge modification corrections."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore
        from sentinel.core.types import Correction

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Add an edge modification correction
            store = CorrectionStore()
            store.add_correction(
                Correction(
                    node_id="person-aunt-susan",
                    action="modify_relationship",
                    new_value="ENERGIZES",
                    target_node_id="energystate-drained",
                    edge_relationship="DRAINS",
                ),
                reason="Test modification",
            )

            result = runner.invoke(main, ["correct", "list"])

        assert result.exit_code == 0, f"Should succeed: {result.output}"
        assert "MODIFY" in result.output.upper() or "modify" in result.output.lower(), (
            f"Should show modify correction: {result.output}"
        )

    def test_correct_list_shows_edge_removals(
        self, runner: CliRunner, tmp_path: Path, graph_with_edge_for_modify: Graph
    ) -> None:
        """correct list displays edge removal corrections."""
        from sentinel.cli.commands import main
        from sentinel.core.persistence import CorrectionStore
        from sentinel.core.types import Correction

        setup_graph_file(tmp_path, graph_with_edge_for_modify)

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # Add an edge removal correction
            store = CorrectionStore()
            store.add_correction(
                Correction(
                    node_id="person-aunt-susan",
                    action="remove_edge",
                    target_node_id="energystate-drained",
                ),
                reason="Test removal",
            )

            result = runner.invoke(main, ["correct", "list"])

        assert result.exit_code == 0, f"Should succeed: {result.output}"
        assert "REMOVE" in result.output.upper() or "remove" in result.output.lower(), (
            f"Should show remove correction: {result.output}"
        )
