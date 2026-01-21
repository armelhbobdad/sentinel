"""Unit tests for CogneeEngine.mutate() method (Story 3.1 Task 2).

Tests node deletion with cascading edge removal and user-stated protection.
"""

import pytest

from sentinel.core.types import Correction, Edge, Graph, Node


class TestMutateDeleteNode:
    """Tests for mutate() with delete action (AC: #1, #3)."""

    def test_mutate_delete_removes_node(self) -> None:
        """mutate(delete) removes the specified node from graph."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="delete")
        result = engine.mutate(graph, correction)

        assert len(result.nodes) == 1, f"Expected 1 node, got {len(result.nodes)}"
        assert result.nodes[0].id == "person-maya", (
            f"Expected Maya to remain, got {result.nodes[0]}"
        )

    def test_mutate_delete_cascades_edges_as_source(self) -> None:
        """mutate(delete) removes all edges where deleted node is source (AC: #3)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
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
            ),
            edges=(
                Edge(
                    source_id="energystate-drained",
                    target_id="energystate-focused",
                    relationship="CONFLICTS_WITH",
                    confidence=0.8,
                ),
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.9,
                ),
            ),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="delete")
        result = engine.mutate(graph, correction)

        # Both edges should be removed (one as source, one as target)
        assert len(result.edges) == 0, f"Expected 0 edges, got {len(result.edges)}"

    def test_mutate_delete_cascades_edges_as_target(self) -> None:
        """mutate(delete) removes all edges where deleted node is target (AC: #3)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="delete")
        result = engine.mutate(graph, correction)

        assert len(result.edges) == 0, f"Expected 0 edges, got {len(result.edges)}"
        assert len(result.nodes) == 1, f"Expected 1 node, got {len(result.nodes)}"

    def test_mutate_delete_preserves_unrelated_nodes_and_edges(self) -> None:
        """mutate(delete) preserves nodes and edges not connected to deleted node."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(id="activity-meeting", label="Meeting", type="Activity", source="user-stated"),
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
                    target_id="activity-meeting",
                    relationship="INVOLVES",
                    confidence=0.95,
                ),
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.9,
                ),
            ),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="delete")
        result = engine.mutate(graph, correction)

        assert len(result.nodes) == 2, f"Expected 2 nodes, got {len(result.nodes)}"
        assert len(result.edges) == 1, f"Expected 1 edge, got {len(result.edges)}"
        assert result.edges[0].relationship == "INVOLVES", (
            f"Expected INVOLVES edge, got {result.edges[0]}"
        )

    def test_mutate_delete_returns_immutable_graph(self) -> None:
        """mutate() returns a new immutable Graph instance."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="delete")
        result = engine.mutate(graph, correction)

        # Verify original is unchanged
        assert len(graph.nodes) == 1, "Original graph should be unchanged"
        # Verify result is a different object
        assert result is not graph, "Result should be a new Graph instance"
        # Verify result is immutable (Graph is frozen dataclass)
        assert len(result.nodes) == 0, f"Result should have 0 nodes, got {len(result.nodes)}"


class TestMutateUserStatedProtection:
    """Tests for user-stated node protection (AC: #2)."""

    def test_mutate_cannot_delete_user_stated_node(self) -> None:
        """mutate() raises ValueError when trying to delete user-stated node (AC: #2)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(Node(id="person-maya", label="Maya", type="Person", source="user-stated"),),
            edges=(),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="person-maya", action="delete")

        with pytest.raises(ValueError) as exc_info:
            engine.mutate(graph, correction)

        assert "user-stated" in str(exc_info.value).lower(), (
            f"Error should mention user-stated: {exc_info.value}"
        )

    def test_mutate_error_message_suggests_paste_command(self) -> None:
        """mutate() error for user-stated nodes suggests using paste command."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(Node(id="person-maya", label="Maya", type="Person", source="user-stated"),),
            edges=(),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="person-maya", action="delete")

        with pytest.raises(ValueError) as exc_info:
            engine.mutate(graph, correction)

        assert "paste" in str(exc_info.value).lower(), (
            f"Error should mention paste: {exc_info.value}"
        )


class TestMutateNodeNotFound:
    """Tests for node not found scenario."""

    def test_mutate_raises_on_node_not_found(self) -> None:
        """mutate() raises KeyError when node doesn't exist."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(Node(id="person-maya", label="Maya", type="Person", source="user-stated"),),
            edges=(),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="nonexistent-node", action="delete")

        with pytest.raises(KeyError) as exc_info:
            engine.mutate(graph, correction)

        assert "nonexistent-node" in str(exc_info.value), (
            f"Error should contain node ID: {exc_info.value}"
        )


class TestMutateUnknownAction:
    """Tests for unknown correction actions."""

    def test_mutate_raises_on_unknown_action(self) -> None:
        """mutate() raises ValueError for unknown action."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        engine = CogneeEngine()
        correction = Correction(node_id="energystate-drained", action="unknown-action")

        with pytest.raises(ValueError) as exc_info:
            engine.mutate(graph, correction)

        assert (
            "unknown" in str(exc_info.value).lower() or "action" in str(exc_info.value).lower()
        ), f"Error should mention unknown action: {exc_info.value}"


# Story 3-2: Edge operation tests


class TestMutateModifyRelationship:
    """Tests for mutate() with modify_relationship action (Story 3-2 Task 2)."""

    def test_mutate_modify_relationship_changes_edge_type(self) -> None:
        """mutate(modify_relationship) changes edge relationship type (AC: #1)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
        )
        result = engine.mutate(graph, correction)

        assert len(result.nodes) == 2, f"Expected 2 nodes, got {len(result.nodes)}"
        assert len(result.edges) == 1, f"Expected 1 edge, got {len(result.edges)}"
        assert result.edges[0].relationship == "ENERGIZES", (
            f"Expected ENERGIZES, got {result.edges[0].relationship}"
        )

    def test_mutate_modify_relationship_preserves_other_edges(self) -> None:
        """mutate(modify_relationship) preserves edges not targeted."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
        )
        result = engine.mutate(graph, correction)

        assert len(result.edges) == 2, f"Expected 2 edges, got {len(result.edges)}"
        edge_types = {e.relationship for e in result.edges}
        assert edge_types == {"ENERGIZES", "INVOLVES"}, f"Got edge types: {edge_types}"

    def test_mutate_modify_relationship_validates_type(self) -> None:
        """mutate(modify_relationship) validates new relationship type."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="INVALID_TYPE",
            target_node_id="energystate-drained",
        )

        with pytest.raises(ValueError) as exc_info:
            engine.mutate(graph, correction)

        assert "invalid" in str(exc_info.value).lower(), (
            f"Error should mention invalid: {exc_info.value}"
        )

    def test_mutate_modify_relationship_edge_not_found(self) -> None:
        """mutate(modify_relationship) raises KeyError when edge not found."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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
            edges=(),  # No edges
        )

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
        )

        with pytest.raises(KeyError):
            engine.mutate(graph, correction)

    def test_mutate_modify_allows_user_stated_edges(self) -> None:
        """mutate(modify_relationship) allows modifications to user-stated edges (AC: #5)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
            nodes=(
                Node(
                    id="person-aunt-susan",
                    label="Aunt Susan",
                    type="Person",
                    source="user-stated",
                ),
                Node(
                    id="energystate-happy",
                    label="happy",
                    type="EnergyState",
                    source="user-stated",  # User-stated node
                ),
            ),
            edges=(
                Edge(
                    source_id="person-aunt-susan",
                    target_id="energystate-happy",
                    relationship="DRAINS",
                    confidence=1.0,  # High confidence = user-stated
                ),
            ),
        )

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-happy",
        )
        # Should NOT raise - user can refine their own statements
        result = engine.mutate(graph, correction)

        assert result.edges[0].relationship == "ENERGIZES"


class TestMutateRemoveEdge:
    """Tests for mutate() with remove_edge action (Story 3-2 Task 2)."""

    def test_mutate_remove_edge_preserves_nodes(self) -> None:
        """mutate(remove_edge) removes edge but keeps both nodes (AC: #2)."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="remove_edge",
            target_node_id="energystate-drained",
        )
        result = engine.mutate(graph, correction)

        assert len(result.nodes) == 2, f"Expected 2 nodes, got {len(result.nodes)}"
        assert len(result.edges) == 0, f"Expected 0 edges, got {len(result.edges)}"

    def test_mutate_remove_edge_preserves_other_edges(self) -> None:
        """mutate(remove_edge) only removes the specified edge."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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
                    id="energystate-exhausted",
                    label="exhausted",
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
                    target_id="energystate-exhausted",
                    relationship="DRAINS",
                    confidence=0.7,
                ),
            ),
        )

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="remove_edge",
            target_node_id="energystate-drained",
        )
        result = engine.mutate(graph, correction)

        assert len(result.edges) == 1, f"Expected 1 edge, got {len(result.edges)}"
        assert result.edges[0].target_id == "energystate-exhausted", (
            f"Expected edge to exhausted, got {result.edges[0]}"
        )

    def test_mutate_remove_edge_not_found(self) -> None:
        """mutate(remove_edge) raises KeyError when edge not found."""
        from sentinel.core.engine import CogneeEngine

        graph = Graph(
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
            edges=(),  # No edges
        )

        engine = CogneeEngine()
        correction = Correction(
            node_id="person-aunt-susan",
            action="remove_edge",
            target_node_id="energystate-drained",
        )

        with pytest.raises(KeyError):
            engine.mutate(graph, correction)
