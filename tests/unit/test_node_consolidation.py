"""Unit tests for semantic node consolidation (BUG-003).

Tests for energy state keyword constants, node grouping,
canonical node selection, and graph consolidation.
"""

import pytest

from sentinel.core.consolidation import (
    compute_similarity,
    consolidate_semantic_nodes,
    group_similar_nodes,
    select_canonical_node,
)
from sentinel.core.constants import (
    ENERGY_STATE_KEYWORDS,
    NODE_SIMILARITY_THRESHOLD,
)
from sentinel.core.types import Edge, Graph, Node


class TestEnergyStateKeywordConstants:
    """Tests for Task 1: Energy state keyword constants."""

    def test_energy_state_keywords_is_frozenset(self) -> None:
        """ENERGY_STATE_KEYWORDS should be immutable frozenset."""
        assert isinstance(ENERGY_STATE_KEYWORDS, frozenset)

    def test_energy_state_keywords_not_empty(self) -> None:
        """ENERGY_STATE_KEYWORDS should contain keywords."""
        assert len(ENERGY_STATE_KEYWORDS) > 0

    def test_energy_state_keywords_contains_energy(self) -> None:
        """Should include 'energy' keyword."""
        assert "energy" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_exhaustion(self) -> None:
        """Should include 'exhaustion' keyword."""
        assert "exhaustion" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_drain(self) -> None:
        """Should include 'drain' keyword."""
        assert "drain" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_fatigue(self) -> None:
        """Should include 'fatigue' keyword."""
        assert "fatigue" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_focus(self) -> None:
        """Should include 'focus' keyword."""
        assert "focus" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_concentration(self) -> None:
        """Should include 'concentration' keyword."""
        assert "concentration" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_tired(self) -> None:
        """Should include 'tired' keyword."""
        assert "tired" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_depleted(self) -> None:
        """Should include 'depleted' keyword."""
        assert "depleted" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_alertness(self) -> None:
        """Should include 'alertness' keyword."""
        assert "alertness" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_sharpness(self) -> None:
        """Should include 'sharpness' keyword."""
        assert "sharpness" in ENERGY_STATE_KEYWORDS

    def test_energy_state_keywords_contains_mental(self) -> None:
        """Should include 'mental' keyword."""
        assert "mental" in ENERGY_STATE_KEYWORDS

    def test_node_similarity_threshold_is_int(self) -> None:
        """NODE_SIMILARITY_THRESHOLD should be integer (0-100 scale)."""
        assert isinstance(NODE_SIMILARITY_THRESHOLD, int)

    def test_node_similarity_threshold_in_valid_range(self) -> None:
        """Threshold should be between 0 and 100."""
        assert 0 <= NODE_SIMILARITY_THRESHOLD <= 100

    def test_node_similarity_threshold_default_value(self) -> None:
        """Default threshold should be 70 (balanced precision/recall)."""
        assert NODE_SIMILARITY_THRESHOLD == 70

    def test_energy_state_keywords_all_lowercase(self) -> None:
        """All keywords should be lowercase for consistent matching."""
        for keyword in ENERGY_STATE_KEYWORDS:
            assert keyword == keyword.lower(), f"Keyword '{keyword}' should be lowercase"


class TestComputeSimilarity:
    """Tests for Task 2: Similarity computation with energy keyword boost."""

    def test_identical_labels_returns_100(self) -> None:
        """Identical labels should have 100% similarity."""
        score = compute_similarity("energy_drain", "energy_drain")
        assert score == 100

    def test_completely_different_labels_low_score(self) -> None:
        """Completely different labels should have low similarity."""
        score = compute_similarity("energy_drain", "presentation")
        assert score < 50

    def test_energy_keywords_get_boosted(self) -> None:
        """Labels with energy keywords and lexical similarity get boost."""
        # Boost only applies when: both have energy keywords AND base similarity >= 40
        # emotional_energy vs emotional_exhaustion: share "emotional" prefix + energy keywords
        score = compute_similarity("emotional_energy", "emotional_exhaustion")
        # Should be boosted to 100 (high base + boost, capped at 100)
        assert score >= 70  # Boosted above merge threshold

    def test_no_boost_without_energy_keywords(self) -> None:
        """Labels without energy keywords don't get boosted."""
        score = compute_similarity("dinner", "aunt_susan")
        # No energy keywords, no boost
        assert score < 50

    def test_partial_match_scores_reasonably(self) -> None:
        """Partial matches should score between 0 and 100."""
        # Using non-energy labels to avoid the boost
        score = compute_similarity("presentation", "present")
        assert 0 < score < 100

    def test_case_insensitive_matching(self) -> None:
        """Matching should be case insensitive."""
        score1 = compute_similarity("Energy_Drain", "energy_drain")
        score2 = compute_similarity("energy_drain", "ENERGY_DRAIN")
        assert score1 == score2 == 100


class TestGroupSimilarNodes:
    """Tests for Task 2: Node grouping by semantic similarity."""

    def _make_node(self, id: str, label: str, type: str = "EnergyState") -> Node:
        """Create a test node."""
        return Node(id=id, label=label, type=type, source="ai-inferred")

    def test_empty_list_returns_empty_groups(self) -> None:
        """Empty node list should return empty groups."""
        groups = group_similar_nodes([])
        assert groups == []

    def test_single_node_returns_single_group(self) -> None:
        """Single node should return one group containing that node."""
        node = self._make_node("1", "energy_drain")
        groups = group_similar_nodes([node])
        assert len(groups) == 1
        assert groups[0] == [node]

    def test_identical_labels_grouped_together(self) -> None:
        """Nodes with identical labels should be grouped together."""
        node1 = self._make_node("1", "energy_drain")
        node2 = self._make_node("2", "energy_drain")
        groups = group_similar_nodes([node1, node2])
        assert len(groups) == 1
        # Compare by ID since Node contains unhashable dict
        assert {n.id for n in groups[0]} == {"1", "2"}

    def test_dissimilar_nodes_separate_groups(self) -> None:
        """Nodes with very different labels should be in separate groups."""
        node1 = self._make_node("1", "energy_drain")
        node2 = self._make_node("2", "presentation")
        groups = group_similar_nodes([node1, node2])
        assert len(groups) == 2

    def test_similar_energy_nodes_grouped(self) -> None:
        """Nodes with similar energy-related labels should be grouped."""
        node1 = self._make_node("1", "emotional_exhaustion")
        node2 = self._make_node("2", "low_energy")
        node3 = self._make_node("3", "energy_drain")
        # low_energy and energy_drain group together (score 54 + 50 boost = 100)
        # emotional_exhaustion stays separate (scores 30 and 37 < 40 threshold for boost)
        groups = group_similar_nodes([node1, node2, node3])
        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

    def test_custom_threshold_respected(self) -> None:
        """Custom similarity threshold should be respected."""
        node1 = self._make_node("1", "energy_drain")
        node2 = self._make_node("2", "drain")
        # High threshold - less grouping
        groups_high = group_similar_nodes([node1, node2], threshold=90)
        # Low threshold - more grouping
        groups_low = group_similar_nodes([node1, node2], threshold=50)
        # High threshold should result in more separate groups
        assert len(groups_high) >= len(groups_low)

    def test_nodes_not_duplicated_across_groups(self) -> None:
        """Each node should appear in exactly one group."""
        nodes = [
            self._make_node("1", "energy_drain"),
            self._make_node("2", "low_energy"),
            self._make_node("3", "presentation"),
        ]
        groups = group_similar_nodes(nodes)
        all_nodes_in_groups = [n for group in groups for n in group]
        assert len(all_nodes_in_groups) == len(nodes)
        assert set(n.id for n in all_nodes_in_groups) == {"1", "2", "3"}


class TestSelectCanonicalNode:
    """Tests for Task 3: Canonical node selection."""

    def _make_node(self, id: str, label: str, type: str = "EnergyState") -> Node:
        """Create a test node."""
        return Node(id=id, label=label, type=type, source="ai-inferred")

    def test_single_node_returns_that_node(self) -> None:
        """Single node group should return that node."""
        node = self._make_node("1", "energy_drain")
        canonical = select_canonical_node([node])
        assert canonical == node

    def test_shortest_label_selected(self) -> None:
        """Shortest label should be selected as canonical."""
        node1 = self._make_node("1", "emotional_exhaustion")  # 20 chars
        node2 = self._make_node("2", "energy")  # 6 chars
        node3 = self._make_node("3", "low_energy")  # 10 chars
        canonical = select_canonical_node([node1, node2, node3])
        assert canonical.id == "2"  # "energy" is shortest

    def test_alphabetical_tiebreaker(self) -> None:
        """Equal length labels should be sorted alphabetically."""
        node1 = self._make_node("1", "drain")  # 5 chars
        node2 = self._make_node("2", "alert")  # 5 chars
        node3 = self._make_node("3", "brain")  # 5 chars
        canonical = select_canonical_node([node1, node2, node3])
        assert canonical.id == "2"  # "alert" is first alphabetically

    def test_empty_group_raises_error(self) -> None:
        """Empty group should raise ValueError."""
        with pytest.raises(ValueError, match="empty group"):
            select_canonical_node([])


class TestConsolidateSemanticNodes:
    """Tests for Task 4: Graph consolidation."""

    def _make_node(self, id: str, label: str, type: str = "EnergyState") -> Node:
        """Create a test node."""
        return Node(id=id, label=label, type=type, source="ai-inferred")

    def _make_edge(self, source_id: str, target_id: str, relationship: str = "DRAINS") -> Edge:
        """Create a test edge."""
        return Edge(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            confidence=1.0,
        )

    def test_empty_graph_returns_empty(self) -> None:
        """Empty graph should return empty graph."""
        graph = Graph(nodes=(), edges=())
        result = consolidate_semantic_nodes(graph)
        assert result.nodes == ()
        assert result.edges == ()

    def test_no_similar_nodes_unchanged(self) -> None:
        """Graph with dissimilar nodes should be unchanged."""
        nodes = (
            self._make_node("1", "dinner"),
            self._make_node("2", "presentation"),
        )
        edges = (self._make_edge("1", "2", "SCHEDULED_BEFORE"),)
        graph = Graph(nodes=nodes, edges=edges)
        result = consolidate_semantic_nodes(graph)
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

    def test_similar_nodes_merged(self) -> None:
        """Similar nodes should be merged into canonical."""
        nodes = (
            self._make_node("1", "energy_drain"),  # shorter = canonical
            self._make_node("2", "energy_drain_state"),
        )
        graph = Graph(nodes=nodes, edges=())
        result = consolidate_semantic_nodes(graph)
        # Two similar nodes should merge into one
        assert len(result.nodes) == 1
        assert result.nodes[0].label == "energy_drain"

    def test_edge_references_rewritten(self) -> None:
        """Edge source/target should be rewritten to canonical IDs."""
        nodes = (
            self._make_node("1", "dinner"),
            self._make_node("2", "energy_drain"),  # canonical
            self._make_node("3", "energy_drain_deep"),  # similar to 2
            self._make_node("4", "presentation"),
        )
        edges = (
            self._make_edge("1", "3", "DRAINS"),  # target 3 → should become 2
            self._make_edge("2", "4", "CONFLICTS_WITH"),
        )
        graph = Graph(nodes=nodes, edges=edges)
        result = consolidate_semantic_nodes(graph)

        # Node 3 should be merged into node 2
        assert len(result.nodes) == 3

        # First edge's target should be rewritten to "2"
        drains_edge = next(e for e in result.edges if e.relationship == "DRAINS")
        assert drains_edge.target_id == "2"

    def test_original_graph_unchanged(self) -> None:
        """Original graph should not be modified (immutability)."""
        nodes = (
            self._make_node("1", "energy_drain"),
            self._make_node("2", "energy_drain_deep"),
        )
        original_nodes = nodes
        graph = Graph(nodes=nodes, edges=())
        _ = consolidate_semantic_nodes(graph)
        # Original graph should be unchanged
        assert graph.nodes == original_nodes

    def test_preserves_edge_metadata(self) -> None:
        """Edge metadata should be preserved during rewrite."""
        nodes = (
            self._make_node("1", "energy"),
            self._make_node("2", "energy_drain"),
        )
        edge = Edge(
            source_id="1",
            target_id="2",
            relationship="DRAINS",
            confidence=0.85,
            metadata={"custom": "value"},
        )
        graph = Graph(nodes=nodes, edges=(edge,))
        result = consolidate_semantic_nodes(graph)
        assert len(result.edges) == 1
        assert result.edges[0].confidence == 0.85
        assert result.edges[0].metadata == {"custom": "value"}
