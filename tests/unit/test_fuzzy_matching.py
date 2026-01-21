"""Unit tests for fuzzy node matching (Story 3.1 Task 3).

Tests fuzzy_find_node() function for node lookup with suggestions.
"""

from sentinel.core.types import Graph, Node


class TestFuzzyFindNode:
    """Tests for fuzzy_find_node() function (AC: #7, #8)."""

    def test_exact_match_returns_node(self) -> None:
        """fuzzy_find_node() returns exact match when available."""
        from sentinel.core.matching import fuzzy_find_node

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

        result = fuzzy_find_node(graph, "Drained")

        assert result is not None, "Should find exact match"
        assert result.match is not None, "Should have match"
        assert result.match.id == "energystate-drained", (
            f"Expected drained node, got {result.match}"
        )
        assert result.is_exact, "Should be exact match"

    def test_exact_match_case_insensitive(self) -> None:
        """fuzzy_find_node() exact match is case insensitive."""
        from sentinel.core.matching import fuzzy_find_node

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

        result = fuzzy_find_node(graph, "DRAINED")

        assert result is not None, "Should find case-insensitive match"
        assert result.match is not None, "Should have match"
        assert result.is_exact, "Case-insensitive should count as exact"

    def test_fuzzy_match_above_threshold(self) -> None:
        """fuzzy_find_node() returns fuzzy match above 70% threshold."""
        from sentinel.core.matching import fuzzy_find_node

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

        # "Drainned" should match "Drained" with high similarity
        result = fuzzy_find_node(graph, "Drainned")

        assert result is not None, "Should find fuzzy match"
        assert result.match is not None, f"Should have match, got suggestions: {result.suggestions}"
        assert result.match.id == "energystate-drained", (
            f"Expected drained node, got {result.match}"
        )
        assert not result.is_exact, "Should not be exact match"

    def test_no_match_returns_suggestions(self) -> None:
        """fuzzy_find_node() returns suggestions when no match found (AC: #7)."""
        from sentinel.core.matching import fuzzy_find_node

        graph = Graph(
            nodes=(
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
                Node(
                    id="energystate-tired", label="Tired", type="EnergyState", source="ai-inferred"
                ),
                Node(
                    id="energystate-exhausted",
                    label="Exhausted",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        result = fuzzy_find_node(graph, "zzzzz")

        assert result is not None, "Should return result"
        assert result.match is None, "Should have no match for garbage input"
        assert len(result.suggestions) > 0, "Should have suggestions"

    def test_only_ai_inferred_nodes_matched(self) -> None:
        """fuzzy_find_node() only matches ai-inferred nodes, not user-stated."""
        from sentinel.core.matching import fuzzy_find_node

        graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-maya",
                    label="Maya's State",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        # When searching for "Maya", should only match ai-inferred node
        result = fuzzy_find_node(graph, "Maya")

        if result.match is not None:
            # If a match is found, it should be ai-inferred
            assert result.match.source == "ai-inferred", (
                f"Should only match ai-inferred nodes, got {result.match.source}"
            )

    def test_ambiguous_match_returns_multiple_candidates(self) -> None:
        """fuzzy_find_node() returns multiple candidates for ambiguous matches (AC: #8)."""
        from sentinel.core.matching import fuzzy_find_node

        graph = Graph(
            nodes=(
                Node(
                    id="energystate-tired1",
                    label="Tired Morning",
                    type="EnergyState",
                    source="ai-inferred",
                ),
                Node(
                    id="energystate-tired2",
                    label="Tired Evening",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        result = fuzzy_find_node(graph, "Tired")

        # Should have multiple candidates since "Tired" is ambiguous
        assert result is not None, "Should return result"
        # If match is None, suggestions should have multiple candidates
        if result.match is None:
            assert len(result.candidates) >= 2, (
                f"Should have multiple candidates, got {result.candidates}"
            )

    def test_empty_graph_returns_no_match(self) -> None:
        """fuzzy_find_node() handles empty graph gracefully."""
        from sentinel.core.matching import fuzzy_find_node

        graph = Graph(nodes=(), edges=())

        result = fuzzy_find_node(graph, "Drained")

        assert result is not None, "Should return result"
        assert result.match is None, "Should have no match"
        assert result.suggestions == [], "Should have no suggestions"


class TestFuzzyFindNodeByID:
    """Tests for fuzzy_find_node() with node ID lookup."""

    def test_exact_id_match(self) -> None:
        """fuzzy_find_node() can match by node ID."""
        from sentinel.core.matching import fuzzy_find_node

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

        result = fuzzy_find_node(graph, "energystate-drained", match_by="id")

        assert result is not None, "Should return result"
        assert result.match is not None, "Should have match"
        assert result.match.id == "energystate-drained", (
            f"Expected drained node, got {result.match}"
        )


class TestMatchResult:
    """Tests for MatchResult structure."""

    def test_match_result_has_required_fields(self) -> None:
        """MatchResult has match, is_exact, suggestions, candidates fields."""
        from sentinel.core.matching import fuzzy_find_node

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

        result = fuzzy_find_node(graph, "Drained")

        assert hasattr(result, "match"), "Should have match field"
        assert hasattr(result, "is_exact"), "Should have is_exact field"
        assert hasattr(result, "suggestions"), "Should have suggestions field"
        assert hasattr(result, "candidates"), "Should have candidates field"
