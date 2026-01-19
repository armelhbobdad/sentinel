"""Core module integration tests.

These tests verify that all core types, constants, and engine components
are properly importable and work together correctly.
"""

import pytest


class TestTypeImports:
    """Tests for verifying type imports work correctly."""

    def test_import_all_types_from_core_types(self) -> None:
        """All core types should be importable from sentinel.core.types."""
        from sentinel.core.types import Correction, Edge, Graph, Node, ScoredCollision

        # Verify all types are classes
        assert callable(Node), "Node should be a class"
        assert callable(Edge), "Edge should be a class"
        assert callable(Graph), "Graph should be a class"
        assert callable(ScoredCollision), "ScoredCollision should be a class"
        assert callable(Correction), "Correction should be a class"

    def test_import_all_constants_from_core_constants(self) -> None:
        """All constants should be importable from sentinel.core.constants."""
        from sentinel.core.constants import (
            DEFAULT_TIMEOUT,
            EXIT_CONFIG_ERROR,
            EXIT_INTERNAL_ERROR,
            EXIT_SUCCESS,
            EXIT_USER_ERROR,
            HIGH_CONFIDENCE,
            MAX_DEPTH,
            MEDIUM_CONFIDENCE,
        )

        # Verify constants have correct types
        assert isinstance(EXIT_SUCCESS, int), "EXIT_SUCCESS should be int"
        assert isinstance(EXIT_USER_ERROR, int), "EXIT_USER_ERROR should be int"
        assert isinstance(EXIT_INTERNAL_ERROR, int), "EXIT_INTERNAL_ERROR should be int"
        assert isinstance(EXIT_CONFIG_ERROR, int), "EXIT_CONFIG_ERROR should be int"
        assert isinstance(MAX_DEPTH, int), "MAX_DEPTH should be int"
        assert isinstance(DEFAULT_TIMEOUT, int), "DEFAULT_TIMEOUT should be int"
        assert isinstance(HIGH_CONFIDENCE, float), "HIGH_CONFIDENCE should be float"
        assert isinstance(MEDIUM_CONFIDENCE, float), "MEDIUM_CONFIDENCE should be float"

    def test_import_engine_components(self) -> None:
        """Engine protocol and implementations should be importable."""
        from sentinel.core.engine import CogneeEngine, GraphEngine, Subgraph

        assert GraphEngine is not None, "GraphEngine should be defined"
        assert CogneeEngine is not None, "CogneeEngine should be defined"
        assert Subgraph is not None, "Subgraph should be defined"

    def test_import_mock_engine_from_conftest(self) -> None:
        """MockEngine should be importable from tests.conftest."""
        from tests.conftest import MockEngine

        assert MockEngine is not None, "MockEngine should be defined"


class TestConstantsValues:
    """Tests for verifying constants have expected values."""

    def test_exit_codes_have_expected_values(self) -> None:
        """Exit codes should match expected Unix convention values."""
        from sentinel.core.constants import (
            EXIT_CONFIG_ERROR,
            EXIT_INTERNAL_ERROR,
            EXIT_SUCCESS,
            EXIT_USER_ERROR,
        )

        assert EXIT_SUCCESS == 0, f"EXIT_SUCCESS should be 0, got {EXIT_SUCCESS}"
        assert EXIT_USER_ERROR == 1, f"EXIT_USER_ERROR should be 1, got {EXIT_USER_ERROR}"
        assert EXIT_INTERNAL_ERROR == 2, (
            f"EXIT_INTERNAL_ERROR should be 2, got {EXIT_INTERNAL_ERROR}"
        )
        assert EXIT_CONFIG_ERROR == 3, f"EXIT_CONFIG_ERROR should be 3, got {EXIT_CONFIG_ERROR}"

    def test_traversal_constants_have_expected_values(self) -> None:
        """Traversal constants should have expected values."""
        from sentinel.core.constants import DEFAULT_TIMEOUT, MAX_DEPTH

        assert MAX_DEPTH == 3, f"MAX_DEPTH should be 3, got {MAX_DEPTH}"
        assert DEFAULT_TIMEOUT == 5, f"DEFAULT_TIMEOUT should be 5, got {DEFAULT_TIMEOUT}"

    def test_confidence_thresholds_have_expected_values(self) -> None:
        """Confidence thresholds should have expected values."""
        from sentinel.core.constants import HIGH_CONFIDENCE, MEDIUM_CONFIDENCE

        assert HIGH_CONFIDENCE == 0.8, f"HIGH_CONFIDENCE should be 0.8, got {HIGH_CONFIDENCE}"
        assert MEDIUM_CONFIDENCE == 0.5, f"MEDIUM_CONFIDENCE should be 0.5, got {MEDIUM_CONFIDENCE}"


class TestMockEngineDeterminism:
    """Tests for verifying MockEngine returns deterministic data."""

    @pytest.mark.asyncio
    async def test_mock_engine_same_input_same_output(self, mock_engine) -> None:
        """MockEngine should return identical graphs for identical input."""
        text = "Monday: Strategy presentation with the exec team, need to be sharp\n"
        text += "Sunday: Dinner with Aunt Susan - always emotionally draining\n"

        graph1 = await mock_engine.ingest(text)
        graph2 = await mock_engine.ingest(text)

        assert graph1.nodes == graph2.nodes, "Same input should produce same nodes"
        assert graph1.edges == graph2.edges, "Same input should produce same edges"

    @pytest.mark.asyncio
    async def test_mock_engine_different_input_different_output(self, mock_engine) -> None:
        """MockEngine should return different graphs for different scenarios."""
        typical_week = "Sunday: Dinner with Aunt Susan - always emotionally draining"
        boring_week = "Monday: Regular standup\nTuesday: Team lunch"

        graph_typical = await mock_engine.ingest(typical_week)
        graph_boring = await mock_engine.ingest(boring_week)

        # Different scenarios should produce different structures
        assert graph_typical.nodes != graph_boring.nodes, "Different scenarios should differ"

    @pytest.mark.asyncio
    async def test_mock_engine_collision_detection_deterministic(self, mock_engine) -> None:
        """MockEngine collision detection should be deterministic."""
        text = "Sunday: Dinner with Aunt Susan - always emotionally draining\n"
        text += "Monday: Strategy presentation with the exec team\n"

        graph = await mock_engine.ingest(text)
        collisions1 = await mock_engine.query_collisions(graph)
        collisions2 = await mock_engine.query_collisions(graph)

        assert len(collisions1) == len(collisions2), (
            "Same graph should produce same collision count"
        )
        for c1, c2 in zip(collisions1, collisions2, strict=True):
            assert c1.path == c2.path, "Collision paths should be identical"
            assert c1.confidence == c2.confidence, "Collision confidence should be identical"
