"""Integration tests for viz module.

Tests ASCII graph visualization with MockEngine graphs.
"""

import time

import pytest

from sentinel.core.types import Graph
from sentinel.viz import render_ascii


class TestRenderAsciiWithMockEngine:
    """Test render_ascii with MockEngine-produced graphs."""

    @pytest.mark.asyncio
    async def test_render_collision_graph(self, mock_engine, maya_typical_week_text: str) -> None:
        """Test rendering collision scenario graph."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        result = render_ascii(graph)

        # Should have node labels with source-appropriate styling
        assert "[Aunt Susan]" in result, f"Expected [Aunt Susan], got: {result}"
        assert "(Low Energy)" in result, f"Expected (Low Energy), got: {result}"

        # Should have relationships section
        assert "Relationships:" in result, f"Expected Relationships section, got: {result}"
        assert "DRAINS" in result, f"Expected DRAINS relationship, got: {result}"

    @pytest.mark.asyncio
    async def test_render_boring_graph(self, mock_engine, maya_boring_week_text: str) -> None:
        """Test rendering boring scenario graph (no collisions)."""
        graph = await mock_engine.ingest(maya_boring_week_text)

        result = render_ascii(graph)

        # Should have user-stated nodes
        assert "[Regular Standup]" in result, f"Expected [Regular Standup], got: {result}"

        # Should have ai-inferred time slots
        assert "(Monday)" in result, f"Expected (Monday), got: {result}"

        # Should have SCHEDULED_AT relationships
        assert "SCHEDULED_AT" in result, f"Expected SCHEDULED_AT, got: {result}"

    @pytest.mark.asyncio
    async def test_render_unicode_graph(self, mock_engine, maya_edge_cases_text: str) -> None:
        """Test rendering graph with Unicode characters."""
        graph = await mock_engine.ingest(maya_edge_cases_text)

        result = render_ascii(graph)

        # Should preserve Unicode characters
        assert "María" in result, f"Expected María in output, got: {result}"
        assert "☕" in result, f"Expected ☕ emoji in output, got: {result}"
        assert "日本語" in result, f"Expected Japanese text in output, got: {result}"


class TestEmptyGraphIntegration:
    """Test empty graph handling in integration context."""

    def test_empty_graph_shows_friendly_message(self) -> None:
        """Test empty graph returns user-friendly message."""
        empty_graph = Graph(nodes=(), edges=())

        result = render_ascii(empty_graph)

        assert "No entities found" in result, f"Expected friendly message, got: {result}"
        assert "Try adding more details" in result, f"Expected tip, got: {result}"


class TestVisualizationPerformance:
    """Test visualization performance meets NFR requirements."""

    @pytest.mark.asyncio
    async def test_typical_graph_renders_quickly(
        self, mock_engine, maya_typical_week_text: str
    ) -> None:
        """Test typical graph (7 nodes, 6 edges) renders in <1 second."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        start = time.time()
        result = render_ascii(graph)
        elapsed = time.time() - start

        assert len(result) > 0, "Expected non-empty output"
        assert elapsed < 1.0, f"Expected <1s render, took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_boring_graph_renders_quickly(
        self, mock_engine, maya_boring_week_text: str
    ) -> None:
        """Test boring graph renders in <1 second."""
        graph = await mock_engine.ingest(maya_boring_week_text)

        start = time.time()
        result = render_ascii(graph)
        elapsed = time.time() - start

        assert len(result) > 0, "Expected non-empty output"
        assert elapsed < 1.0, f"Expected <1s render, took {elapsed:.2f}s"


class TestNodeStylingIntegration:
    """Test node styling with realistic graphs."""

    @pytest.mark.asyncio
    async def test_user_stated_nodes_have_square_brackets(
        self, mock_engine, maya_typical_week_text: str
    ) -> None:
        """Test user-stated nodes use square brackets."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        result = render_ascii(graph)

        # Aunt Susan is user-stated
        assert "[Aunt Susan]" in result, f"Expected [Aunt Susan], got: {result}"
        # Dinner with Aunt Susan is user-stated
        assert "[Dinner with Aunt Susan]" in result, f"Expected [Dinner], got: {result}"

    @pytest.mark.asyncio
    async def test_ai_inferred_nodes_have_parentheses(
        self, mock_engine, maya_typical_week_text: str
    ) -> None:
        """Test AI-inferred nodes use parentheses."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        result = render_ascii(graph)

        # Energy states are ai-inferred
        assert "(Low Energy)" in result, f"Expected (Low Energy), got: {result}"
        assert "(High Focus Required)" in result, f"Expected (High Focus), got: {result}"


class TestEdgeLabelsIntegration:
    """Test edge labels in relationships section."""

    @pytest.mark.asyncio
    async def test_all_relationship_types_shown(
        self, mock_engine, maya_typical_week_text: str
    ) -> None:
        """Test all relationship types appear in output."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        result = render_ascii(graph)

        # Check all relationship types from collision graph
        assert "DRAINS" in result, f"Expected DRAINS, got: {result}"
        assert "INVOLVES" in result, f"Expected INVOLVES, got: {result}"
        assert "CONFLICTS_WITH" in result, f"Expected CONFLICTS_WITH, got: {result}"
        assert "REQUIRES" in result, f"Expected REQUIRES, got: {result}"
        assert "SCHEDULED_AT" in result, f"Expected SCHEDULED_AT, got: {result}"

    @pytest.mark.asyncio
    async def test_edge_labels_use_arrow_notation(
        self, mock_engine, maya_typical_week_text: str
    ) -> None:
        """Test edge labels use --LABEL--> arrow notation."""
        graph = await mock_engine.ingest(maya_typical_week_text)

        result = render_ascii(graph)

        # Check arrow notation
        assert "--DRAINS-->" in result, f"Expected --DRAINS-->, got: {result}"
        assert "--INVOLVES-->" in result, f"Expected --INVOLVES-->, got: {result}"
