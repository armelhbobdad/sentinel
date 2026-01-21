"""Tests for core engine module."""

import pytest


def test_graph_engine_protocol_exists() -> None:
    """GraphEngine protocol should be importable."""
    from sentinel.core.engine import GraphEngine

    assert GraphEngine is not None, "GraphEngine should be defined"


def test_graph_engine_has_async_ingest_method() -> None:
    """GraphEngine should define async ingest method."""
    from typing import get_type_hints

    from sentinel.core.engine import GraphEngine

    hints = get_type_hints(GraphEngine.ingest)
    assert "text" in hints or "return" in hints, "ingest should have type hints"


def test_graph_engine_has_async_query_collisions_method() -> None:
    """GraphEngine should define async query_collisions method."""
    from sentinel.core.engine import GraphEngine

    assert hasattr(GraphEngine, "query_collisions"), "GraphEngine should have query_collisions"


def test_graph_engine_has_async_get_neighbors_method() -> None:
    """GraphEngine should define async get_neighbors method."""
    from sentinel.core.engine import GraphEngine

    assert hasattr(GraphEngine, "get_neighbors"), "GraphEngine should have get_neighbors"


def test_graph_engine_has_sync_mutate_method() -> None:
    """GraphEngine should define sync mutate method."""
    from sentinel.core.engine import GraphEngine

    assert hasattr(GraphEngine, "mutate"), "GraphEngine should have mutate"


def test_graph_engine_has_sync_persist_method() -> None:
    """GraphEngine should define sync persist method."""
    from sentinel.core.engine import GraphEngine

    assert hasattr(GraphEngine, "persist"), "GraphEngine should have persist"


def test_cognee_engine_stub_exists() -> None:
    """CogneeEngine stub class should be importable."""
    from sentinel.core.engine import CogneeEngine

    assert CogneeEngine is not None, "CogneeEngine should be defined"


def test_cognee_engine_implements_protocol() -> None:
    """CogneeEngine should implement GraphEngine protocol."""
    from sentinel.core.engine import CogneeEngine

    # Check that CogneeEngine has all the methods defined in GraphEngine
    protocol_methods = ["ingest", "query_collisions", "get_neighbors", "mutate", "persist", "load"]
    for method in protocol_methods:
        assert hasattr(CogneeEngine, method), f"CogneeEngine should have {method} method"


@pytest.mark.asyncio
@pytest.mark.skipif(
    bool(__import__("os").environ.get("LLM_API_KEY")),
    reason="Test requires no API key to verify error handling",
)
async def test_cognee_engine_ingest_raises_ingestion_error_without_api_key() -> None:
    """CogneeEngine.ingest should raise IngestionError when API key is missing."""
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.exceptions import IngestionError

    engine = CogneeEngine()
    with pytest.raises(IngestionError) as exc_info:
        await engine.ingest("test text")
    assert "Failed to process schedule" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cognee_engine_query_collisions_raises_not_implemented() -> None:
    """CogneeEngine.query_collisions should raise NotImplementedError (stub)."""
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.types import Graph

    engine = CogneeEngine()
    graph = Graph(nodes=(), edges=())
    with pytest.raises(NotImplementedError):
        await engine.query_collisions(graph)


@pytest.mark.asyncio
async def test_cognee_engine_get_neighbors_raises_not_implemented() -> None:
    """CogneeEngine.get_neighbors should raise NotImplementedError (stub)."""
    from sentinel.core.engine import CogneeEngine

    engine = CogneeEngine()
    with pytest.raises(NotImplementedError):
        await engine.get_neighbors("node-1")


def test_cognee_engine_mutate_is_implemented() -> None:
    """CogneeEngine.mutate should be implemented (Story 3.1)."""
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.types import Correction, Graph, Node

    engine = CogneeEngine()
    # Create a graph with an AI-inferred node
    graph = Graph(
        nodes=(Node(id="node-1", label="Test Node", type="EnergyState", source="ai-inferred"),),
        edges=(),
    )
    correction = Correction(node_id="node-1", action="delete", new_value=None)
    # Should not raise - mutate() is now implemented
    result = engine.mutate(graph, correction)
    assert len(result.nodes) == 0, "Node should be deleted"


def test_cognee_engine_persist_is_implemented(tmp_path) -> None:
    """CogneeEngine.persist should be implemented (Story 1.4)."""
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.types import Graph

    # Use temp directory to avoid polluting real data
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XDG_DATA_HOME", str(tmp_path))
        engine = CogneeEngine()
        graph = Graph(nodes=(), edges=())
        # Should not raise - persist() is now implemented
        engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        assert db_path.exists(), "Graph should be persisted to file"
