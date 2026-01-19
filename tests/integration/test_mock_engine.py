"""Tests for MockEngine implementation."""

import pytest


def test_mock_engine_exists() -> None:
    """MockEngine should be importable from conftest."""
    from tests.conftest import MockEngine

    assert MockEngine is not None, "MockEngine should be defined"


def test_mock_engine_fixture_exists(mock_engine) -> None:
    """mock_engine fixture should provide a MockEngine instance."""
    from tests.conftest import MockEngine

    assert isinstance(mock_engine, MockEngine), "mock_engine fixture should provide MockEngine"


@pytest.mark.asyncio
async def test_mock_engine_ingest_returns_graph(mock_engine, maya_typical_week_text: str) -> None:
    """MockEngine.ingest should return a Graph with nodes and edges."""
    from sentinel.core.types import Graph

    graph = await mock_engine.ingest(maya_typical_week_text)

    assert isinstance(graph, Graph), f"Expected Graph, got {type(graph)}"
    assert len(graph.nodes) > 0, f"Expected nodes in graph, got {len(graph.nodes)}"
    assert len(graph.edges) > 0, f"Expected edges in graph, got {len(graph.edges)}"


@pytest.mark.asyncio
async def test_mock_engine_ingest_is_deterministic(
    mock_engine, maya_typical_week_text: str
) -> None:
    """MockEngine.ingest should return same result for same input."""
    graph1 = await mock_engine.ingest(maya_typical_week_text)
    graph2 = await mock_engine.ingest(maya_typical_week_text)

    assert graph1.nodes == graph2.nodes, "Same input should produce same nodes"
    assert graph1.edges == graph2.edges, "Same input should produce same edges"


@pytest.mark.asyncio
async def test_mock_engine_creates_collision_scenario(
    mock_engine, maya_typical_week_text: str
) -> None:
    """MockEngine should create a graph with collision path for typical week."""
    graph = await mock_engine.ingest(maya_typical_week_text)

    # Should have Person node (Aunt Susan)
    person_nodes = [n for n in graph.nodes if n.type == "Person"]
    assert len(person_nodes) > 0, "Expected Person nodes in collision scenario"

    # Should have DRAINS relationship
    drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]
    assert len(drains_edges) > 0, "Expected DRAINS edges for collision scenario"


@pytest.mark.asyncio
async def test_mock_engine_boring_week_has_no_collisions(
    mock_engine, maya_boring_week_text: str
) -> None:
    """MockEngine should create graph without collision path for boring week."""
    graph = await mock_engine.ingest(maya_boring_week_text)

    # Should have nodes but no DRAINS relationships
    assert len(graph.nodes) > 0, "Expected nodes in boring week graph"

    # No collision-inducing relationships
    drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]
    assert len(drains_edges) == 0, "Boring week should not have DRAINS edges"


@pytest.mark.asyncio
async def test_mock_engine_handles_unicode(mock_engine, maya_edge_cases_text: str) -> None:
    """MockEngine should handle Unicode and emoji in fixture."""
    graph = await mock_engine.ingest(maya_edge_cases_text)

    # Should successfully create graph with Unicode content
    assert len(graph.nodes) > 0, "Expected nodes from Unicode fixture"

    # Check that Unicode characters are preserved in labels
    all_labels = [n.label for n in graph.nodes]
    labels_str = " ".join(all_labels)
    assert any(c in labels_str for c in ["María", "☕", "über", "日本語"]), (
        f"Unicode should be preserved in labels: {labels_str}"
    )


@pytest.mark.asyncio
async def test_mock_engine_includes_boundary_confidence_values(
    mock_engine, maya_typical_week_text: str
) -> None:
    """MockEngine should include boundary confidence values for testing."""
    graph = await mock_engine.ingest(maya_typical_week_text)

    confidence_values = [e.confidence for e in graph.edges]

    # Check for boundary values around thresholds
    # MEDIUM_CONFIDENCE = 0.5, HIGH_CONFIDENCE = 0.8
    boundary_values = {0.49, 0.50, 0.51, 0.79, 0.80, 0.81}

    # At least some boundary values should be present
    found_boundaries = set(confidence_values) & boundary_values
    assert len(found_boundaries) >= 3, (
        f"Expected at least 3 boundary confidence values, found {found_boundaries} "
        f"in {confidence_values}"
    )


@pytest.mark.asyncio
async def test_mock_engine_query_collisions_returns_list(
    mock_engine, maya_typical_week_text: str
) -> None:
    """MockEngine.query_collisions should return list of ScoredCollisions."""
    from sentinel.core.types import ScoredCollision

    graph = await mock_engine.ingest(maya_typical_week_text)
    collisions = await mock_engine.query_collisions(graph)

    assert isinstance(collisions, list), f"Expected list, got {type(collisions)}"
    for collision in collisions:
        assert isinstance(collision, ScoredCollision), (
            f"Expected ScoredCollision, got {type(collision)}"
        )


@pytest.mark.asyncio
async def test_mock_engine_typical_week_has_collisions(
    mock_engine, maya_typical_week_text: str
) -> None:
    """MockEngine should detect collisions in typical week."""
    graph = await mock_engine.ingest(maya_typical_week_text)
    collisions = await mock_engine.query_collisions(graph)

    assert len(collisions) > 0, "Expected collisions in typical week"
    assert all(c.confidence > 0 for c in collisions), "Collisions should have confidence > 0"


@pytest.mark.asyncio
async def test_mock_engine_boring_week_collision_detection_returns_empty(
    mock_engine, maya_boring_week_text: str
) -> None:
    """MockEngine should not detect collisions in boring week."""
    graph = await mock_engine.ingest(maya_boring_week_text)
    collisions = await mock_engine.query_collisions(graph)

    assert len(collisions) == 0, f"Expected no collisions in boring week, got {len(collisions)}"


def test_mock_engine_mutate_returns_new_graph(mock_engine) -> None:
    """MockEngine.mutate should return a new Graph."""
    from sentinel.core.types import Correction, Graph, Node

    node = Node(id="n1", label="Test", type="Person", source="ai-inferred", metadata={})
    graph = Graph(nodes=[node], edges=[])
    correction = Correction(node_id="n1", action="delete", new_value=None)

    result = mock_engine.mutate(graph, correction)

    assert isinstance(result, Graph), f"Expected Graph, got {type(result)}"
    # After delete, node should be removed
    assert len(result.nodes) == 0, "Delete correction should remove node"


def test_mock_engine_persist_does_not_raise(mock_engine) -> None:
    """MockEngine.persist should complete without error."""
    from sentinel.core.types import Graph

    graph = Graph(nodes=[], edges=[])

    # Should not raise
    mock_engine.persist(graph)
