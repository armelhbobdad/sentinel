"""Unit tests for confidence filtering and sorting logic.

Story 2.4: Confidence Scoring & Risk Levels.
Tests for filtering low-confidence collisions and sorting by confidence.
"""

import pytest

from sentinel.core.constants import MEDIUM_CONFIDENCE
from sentinel.core.types import ScoredCollision


class TestFilterCollisionsByConfidence:
    """Tests for filter_collisions_by_confidence function (AC #5)."""

    def test_filter_excludes_low_confidence(self) -> None:
        """Test that collisions below threshold are filtered out."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("A", "REL", "B"), confidence=0.9, source_breakdown={}),
            ScoredCollision(path=("C", "REL", "D"), confidence=0.6, source_breakdown={}),
            ScoredCollision(
                path=("E", "REL", "F"), confidence=0.4, source_breakdown={}
            ),  # Should be filtered
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        assert len(filtered) == 2, "Should filter out confidence < 0.5"
        assert all(c.confidence >= MEDIUM_CONFIDENCE for c in filtered), (
            "All remaining should have confidence >= 0.5"
        )

    def test_filter_includes_at_threshold(self) -> None:
        """Test that collisions exactly at threshold are included."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        collisions = [
            ScoredCollision(
                path=("A", "REL", "B"), confidence=0.50, source_breakdown={}
            ),  # Exactly at threshold
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        assert len(filtered) == 1, "Should include collision exactly at threshold"

    def test_filter_boundary_values(self) -> None:
        """Test filtering at exact threshold boundaries (AC #9)."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        collisions = [
            ScoredCollision(
                path=("A",), confidence=0.49, source_breakdown={}
            ),  # Just below - filtered
            ScoredCollision(path=("B",), confidence=0.50, source_breakdown={}),  # Exactly - kept
            ScoredCollision(path=("C",), confidence=0.51, source_breakdown={}),  # Just above - kept
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        assert len(filtered) == 2, "Should keep exactly 2 (0.50 and 0.51)"
        confidences = [c.confidence for c in filtered]
        assert 0.49 not in confidences, "0.49 should be filtered out"
        assert 0.50 in confidences, "0.50 should be kept (at threshold)"
        assert 0.51 in confidences, "0.51 should be kept (above threshold)"

    def test_filter_returns_empty_for_all_low(self) -> None:
        """Test that filtering returns empty list if all below threshold."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("A",), confidence=0.3, source_breakdown={}),
            ScoredCollision(path=("B",), confidence=0.2, source_breakdown={}),
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        assert len(filtered) == 0, "Should return empty list when all below threshold"

    def test_filter_returns_all_when_all_above(self) -> None:
        """Test that filtering keeps all when all above threshold."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("A",), confidence=0.8, source_breakdown={}),
            ScoredCollision(path=("B",), confidence=0.9, source_breakdown={}),
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        assert len(filtered) == 2, "Should keep all when all above threshold"

    def test_filter_handles_empty_list(self) -> None:
        """Test that filtering handles empty input gracefully."""
        from sentinel.cli.commands import filter_collisions_by_confidence

        filtered = filter_collisions_by_confidence([], MEDIUM_CONFIDENCE)

        assert filtered == [], "Should return empty list for empty input"


class TestSortCollisionsByConfidence:
    """Tests for sort_collisions_by_confidence function (AC #7)."""

    def test_sort_descending_order(self) -> None:
        """Test that collisions are sorted by confidence descending."""
        from sentinel.cli.commands import sort_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("A",), confidence=0.5, source_breakdown={}),
            ScoredCollision(path=("B",), confidence=0.9, source_breakdown={}),
            ScoredCollision(path=("C",), confidence=0.7, source_breakdown={}),
        ]

        sorted_collisions = sort_collisions_by_confidence(collisions)

        confidences = [c.confidence for c in sorted_collisions]
        assert confidences == [0.9, 0.7, 0.5], "Should be sorted descending"

    def test_sort_stable_for_equal_confidence(self) -> None:
        """Test that sorting preserves order for equal confidence values."""
        from sentinel.cli.commands import sort_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("First",), confidence=0.7, source_breakdown={}),
            ScoredCollision(path=("Second",), confidence=0.7, source_breakdown={}),
        ]

        sorted_collisions = sort_collisions_by_confidence(collisions)

        # Both have same confidence, order should be preserved (stable sort)
        assert sorted_collisions[0].path[0] == "First", "Stable sort should preserve order"
        assert sorted_collisions[1].path[0] == "Second", "Stable sort should preserve order"

    def test_sort_handles_empty_list(self) -> None:
        """Test that sorting handles empty input gracefully."""
        from sentinel.cli.commands import sort_collisions_by_confidence

        sorted_collisions = sort_collisions_by_confidence([])

        assert sorted_collisions == [], "Should return empty list for empty input"

    def test_sort_handles_single_item(self) -> None:
        """Test that sorting handles single item gracefully."""
        from sentinel.cli.commands import sort_collisions_by_confidence

        collisions = [
            ScoredCollision(path=("A",), confidence=0.5, source_breakdown={}),
        ]

        sorted_collisions = sort_collisions_by_confidence(collisions)

        assert len(sorted_collisions) == 1, "Should return single item list"
        assert sorted_collisions[0].confidence == 0.5, "Value should be preserved"

    def test_sort_preserves_collision_data(self) -> None:
        """Test that sorting doesn't modify collision data."""
        from sentinel.cli.commands import sort_collisions_by_confidence

        original = ScoredCollision(
            path=("Entity", "REL", "Target"),
            confidence=0.75,
            source_breakdown={"user_stated": 1, "ai_inferred": 1},
        )

        sorted_collisions = sort_collisions_by_confidence([original])

        result = sorted_collisions[0]
        assert result.path == original.path, "Path should be preserved"
        assert result.confidence == original.confidence, "Confidence should be preserved"
        assert result.source_breakdown == original.source_breakdown, "Source breakdown preserved"


class TestConfidenceLevelBoundaries:
    """Tests for confidence level boundary value handling (AC #9)."""

    def test_boundary_values_at_medium_threshold(self) -> None:
        """Test exact boundary values around MEDIUM_CONFIDENCE (0.5)."""
        from sentinel.cli.commands import get_confidence_level

        # Just below MEDIUM
        assert get_confidence_level(0.49) == "LOW", "0.49 should be LOW"

        # Exactly at MEDIUM
        assert get_confidence_level(0.50) == "MEDIUM", "0.50 should be MEDIUM"

        # Just above MEDIUM
        assert get_confidence_level(0.51) == "MEDIUM", "0.51 should be MEDIUM"

    def test_boundary_values_at_high_threshold(self) -> None:
        """Test exact boundary values around HIGH_CONFIDENCE (0.8)."""
        from sentinel.cli.commands import get_confidence_level

        # Just below HIGH
        assert get_confidence_level(0.79) == "MEDIUM", "0.79 should be MEDIUM"

        # Exactly at HIGH
        assert get_confidence_level(0.80) == "HIGH", "0.80 should be HIGH"

        # Just above HIGH
        assert get_confidence_level(0.81) == "HIGH", "0.81 should be HIGH"

    def test_comprehensive_threshold_validation(self) -> None:
        """Comprehensive test of all boundary values per Story 2.4 AC #9.

        Validates that threshold classification and filtering work correctly
        at all critical boundary points: 0.49, 0.50, 0.51, 0.79, 0.80, 0.81.
        """
        from sentinel.cli.commands import (
            filter_collisions_by_confidence,
            get_confidence_level,
        )

        # Test cases: (confidence, expected_level, should_show_default)
        test_cases = [
            (0.49, "LOW", False),  # Just below MEDIUM - filtered by default
            (0.50, "MEDIUM", True),  # Exactly MEDIUM - shown by default
            (0.51, "MEDIUM", True),  # Just above MEDIUM - shown
            (0.79, "MEDIUM", True),  # Just below HIGH - shown
            (0.80, "HIGH", True),  # Exactly HIGH - shown
            (0.81, "HIGH", True),  # Just above HIGH - shown
        ]

        # Validate classification
        for confidence, expected_level, _ in test_cases:
            actual_level = get_confidence_level(confidence)
            assert actual_level == expected_level, (
                f"Confidence {confidence} should be {expected_level}, got {actual_level}"
            )

        # Validate filtering
        collisions = [
            ScoredCollision(path=(f"conf-{c}",), confidence=c, source_breakdown={})
            for c, _, _ in test_cases
        ]

        filtered = filter_collisions_by_confidence(collisions, MEDIUM_CONFIDENCE)

        # Expected: 5 collisions shown (0.50, 0.51, 0.79, 0.80, 0.81)
        assert len(filtered) == 5, f"Expected 5 collisions after filtering, got {len(filtered)}"

        # Verify 0.49 was filtered out
        filtered_confidences = {c.confidence for c in filtered}
        assert 0.49 not in filtered_confidences, "0.49 should be filtered out"
        assert 0.50 in filtered_confidences, "0.50 should be included"


class TestMockEngineBoundaryValues:
    """Tests validating MockEngine fixture includes proper boundary values (AC #9)."""

    @pytest.mark.asyncio
    async def test_mockengine_has_boundary_confidence_values(self) -> None:
        """Verify MockEngine collision graph includes boundary confidence values.

        Story 2.4 AC #9: MockEngine fixture data includes boundary values
        (0.49, 0.50, 0.51, 0.79, 0.80, 0.81) to test threshold filtering logic.
        """
        from tests.conftest import MockEngine

        engine = MockEngine()
        graph = await engine.ingest("Dinner with Aunt Susan")

        # Extract all confidence values from edges
        edge_confidences = {edge.confidence for edge in graph.edges}

        # MockEngine should include all boundary values per AC #9
        expected_boundaries = {0.49, 0.50, 0.51, 0.79, 0.80, 0.81}
        found_boundaries = edge_confidences & expected_boundaries

        assert found_boundaries == expected_boundaries, (
            f"MockEngine must include ALL boundary confidence values per AC #9. "
            f"Expected {expected_boundaries}, found {found_boundaries}"
        )
