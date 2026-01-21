"""Unit tests for corrections integration with graph loading (Story 3.1 Task 5).

Tests that corrections are applied when loading graph, ensuring deleted nodes
don't appear in collision detection results.
"""

import os
from pathlib import Path
from unittest.mock import patch

from sentinel.core.types import Correction, Edge, Graph, Node


class TestGraphLoadAppliesCorrections:
    """Tests for CogneeEngine.load() applying corrections (AC: #5)."""

    def test_load_filters_deleted_nodes(self, tmp_path: Path) -> None:
        """load() filters out nodes that have been marked as deleted."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        # Create and persist a graph
        original_graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
                Node(
                    id="energystate-tired", label="Tired", type="EnergyState", source="ai-inferred"
                ),
            ),
            edges=(
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.9,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            # Add a correction to delete a node
            store = CorrectionStore()
            store.add_correction(
                Correction(node_id="energystate-drained", action="delete"),
                reason="Test deletion",
            )

            # Load should apply corrections
            loaded_graph = engine.load(apply_corrections=True)

        assert loaded_graph is not None, "Should load graph"
        node_ids = [n.id for n in loaded_graph.nodes]
        assert "energystate-drained" not in node_ids, (
            f"Deleted node should be filtered out: {node_ids}"
        )
        assert "energystate-tired" in node_ids, "Non-deleted node should remain"
        assert "person-maya" in node_ids, "User-stated node should remain"

    def test_load_filters_edges_of_deleted_nodes(self, tmp_path: Path) -> None:
        """load() filters out edges connected to deleted nodes."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        original_graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.9,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            store = CorrectionStore()
            store.add_correction(
                Correction(node_id="energystate-drained", action="delete"),
                reason="Test deletion",
            )

            loaded_graph = engine.load(apply_corrections=True)

        assert loaded_graph is not None, "Should load graph"
        assert len(loaded_graph.edges) == 0, (
            f"Edges to deleted node should be filtered: {loaded_graph.edges}"
        )

    def test_load_without_corrections_returns_full_graph(self, tmp_path: Path) -> None:
        """load() without apply_corrections=True returns full graph."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        original_graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            store = CorrectionStore()
            store.add_correction(
                Correction(node_id="energystate-drained", action="delete"),
                reason="Test deletion",
            )

            # Load without apply_corrections (default behavior)
            loaded_graph = engine.load(apply_corrections=False)

        assert loaded_graph is not None, "Should load graph"
        node_ids = [n.id for n in loaded_graph.nodes]
        # Without corrections, deleted node should still be present
        assert len(loaded_graph.nodes) == 2, f"Should have all nodes: {node_ids}"


# Story 3-2: Edge correction integration tests


class TestGraphLoadAppliesEdgeCorrections:
    """Tests for CogneeEngine.load() applying edge corrections (Story 3-2 Task 4)."""

    def test_load_applies_modify_relationship_correction(self, tmp_path: Path) -> None:
        """load() applies modify_relationship corrections to edges."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        original_graph = Graph(
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
            ),
            edges=(
                Edge(
                    source_id="person-aunt-susan",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.8,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            # Add a modify_relationship correction
            store = CorrectionStore()
            store.add_correction(
                Correction(
                    node_id="person-aunt-susan",
                    action="modify_relationship",
                    new_value="ENERGIZES",
                    target_node_id="energystate-drained",
                    edge_relationship="DRAINS",
                ),
                reason="Aunt Susan actually energizes me",
            )

            loaded_graph = engine.load(apply_corrections=True)

        assert loaded_graph is not None, "Should load graph"
        assert len(loaded_graph.edges) == 1, f"Should have 1 edge: {loaded_graph.edges}"
        assert loaded_graph.edges[0].relationship == "ENERGIZES", (
            f"Edge should be modified to ENERGIZES: {loaded_graph.edges[0].relationship}"
        )

    def test_load_applies_remove_edge_correction(self, tmp_path: Path) -> None:
        """load() applies remove_edge corrections to edges."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        original_graph = Graph(
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
            ),
            edges=(
                Edge(
                    source_id="person-aunt-susan",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.8,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            # Add a remove_edge correction
            store = CorrectionStore()
            store.add_correction(
                Correction(
                    node_id="person-aunt-susan",
                    action="remove_edge",
                    target_node_id="energystate-drained",
                ),
                reason="Edge is incorrect",
            )

            loaded_graph = engine.load(apply_corrections=True)

        assert loaded_graph is not None, "Should load graph"
        assert len(loaded_graph.nodes) == 2, "Should still have 2 nodes"
        assert len(loaded_graph.edges) == 0, f"Edge should be removed: {loaded_graph.edges}"

    def test_load_preserves_unrelated_edges_with_remove_edge(self, tmp_path: Path) -> None:
        """load() preserves edges not targeted by remove_edge correction."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        original_graph = Graph(
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
                    id="activity-meeting",
                    label="Meeting",
                    type="Activity",
                    source="user-stated",
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
                    target_id="activity-meeting",
                    relationship="INVOLVES",
                    confidence=0.9,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original_graph)

            # Remove only one edge
            store = CorrectionStore()
            store.add_correction(
                Correction(
                    node_id="person-aunt-susan",
                    action="remove_edge",
                    target_node_id="energystate-drained",
                ),
                reason="Edge is incorrect",
            )

            loaded_graph = engine.load(apply_corrections=True)

        assert loaded_graph is not None, "Should load graph"
        assert len(loaded_graph.edges) == 1, f"Should have 1 edge: {loaded_graph.edges}"
        assert loaded_graph.edges[0].relationship == "INVOLVES", (
            f"INVOLVES edge should remain: {loaded_graph.edges[0]}"
        )


class TestCheckCommandAppliesCorrections:
    """Tests for check command applying corrections (AC: #5)."""

    def test_check_does_not_show_deleted_node_collisions(self, tmp_path: Path) -> None:
        """check command should not show collisions involving deleted nodes."""
        from click.testing import CliRunner

        from sentinel.cli.commands import main
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.persistence import CorrectionStore

        runner = CliRunner()
        custom_xdg = str(tmp_path)

        # Create a graph with collision scenario
        collision_graph = Graph(
            nodes=(
                Node(
                    id="person-aunt-susan",
                    label="Aunt Susan",
                    type="Person",
                    source="user-stated",
                    metadata={"domain": "SOCIAL"},
                ),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
                Node(
                    id="energystate-focused",
                    label="Focused",
                    type="EnergyState",
                    source="ai-inferred",
                ),
                Node(
                    id="activity-presentation",
                    label="Strategy Presentation",
                    type="Activity",
                    source="user-stated",
                    metadata={"domain": "PROFESSIONAL"},
                ),
            ),
            edges=(
                Edge(
                    source_id="person-aunt-susan",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.9,
                ),
                Edge(
                    source_id="energystate-drained",
                    target_id="energystate-focused",
                    relationship="CONFLICTS_WITH",
                    confidence=0.85,
                ),
                Edge(
                    source_id="activity-presentation",
                    target_id="energystate-focused",
                    relationship="REQUIRES",
                    confidence=0.9,
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(collision_graph)

            # Delete the "Drained" node that's part of the collision path
            store = CorrectionStore()
            store.add_correction(
                Correction(node_id="energystate-drained", action="delete"),
                reason="User correction",
            )

            # Run check command
            result = runner.invoke(main, ["check"])

        # With the collision-causing node deleted, no collisions should be found
        # The output should indicate no collisions or a success state
        # (depending on implementation, either no collision or success exit)
        assert "Drained" not in result.output, (
            f"Deleted node should not appear in output: {result.output}"
        )
