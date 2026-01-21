"""Tests for core types module."""


def test_node_dataclass_has_required_fields() -> None:
    """Node should have id, label, type, source, and metadata fields."""
    from sentinel.core.types import Node

    node = Node(
        id="node-1",
        label="Aunt Susan",
        type="Person",
        source="user-stated",
        metadata={"notes": "Always draining"},
    )

    assert node.id == "node-1", f"Expected id 'node-1', got {node.id}"
    assert node.label == "Aunt Susan", f"Expected label 'Aunt Susan', got {node.label}"
    assert node.type == "Person", f"Expected type 'Person', got {node.type}"
    assert node.source == "user-stated", f"Expected source 'user-stated', got {node.source}"
    assert node.metadata == {"notes": "Always draining"}


def test_node_source_literal_types() -> None:
    """Node source should accept both 'user-stated' and 'ai-inferred'."""
    from sentinel.core.types import Node

    user_node = Node(id="1", label="Test", type="Person", source="user-stated", metadata={})
    ai_node = Node(id="2", label="Test", type="Person", source="ai-inferred", metadata={})

    assert user_node.source == "user-stated"
    assert ai_node.source == "ai-inferred"


def test_edge_dataclass_has_required_fields() -> None:
    """Edge should have source_id, target_id, relationship, confidence, and metadata fields."""
    from sentinel.core.types import Edge

    edge = Edge(
        source_id="node-1",
        target_id="node-2",
        relationship="DRAINS",
        confidence=0.85,
        metadata={"reason": "emotionally draining"},
    )

    assert edge.source_id == "node-1", f"Expected source_id 'node-1', got {edge.source_id}"
    assert edge.target_id == "node-2", f"Expected target_id 'node-2', got {edge.target_id}"
    assert edge.relationship == "DRAINS", f"Expected relationship 'DRAINS', got {edge.relationship}"
    assert edge.confidence == 0.85, f"Expected confidence 0.85, got {edge.confidence}"
    assert edge.metadata == {"reason": "emotionally draining"}


def test_graph_dataclass_has_nodes_and_edges() -> None:
    """Graph should have nodes and edges lists."""
    from sentinel.core.types import Edge, Graph, Node

    node1 = Node(id="1", label="Person A", type="Person", source="user-stated", metadata={})
    node2 = Node(id="2", label="Activity B", type="Activity", source="ai-inferred", metadata={})
    edge = Edge(source_id="1", target_id="2", relationship="INVOLVES", confidence=0.9, metadata={})

    graph = Graph(nodes=(node1, node2), edges=(edge,))

    assert len(graph.nodes) == 2, f"Expected 2 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) == 1, f"Expected 1 edge, got {len(graph.edges)}"
    assert graph.nodes[0].id == "1"
    assert graph.edges[0].relationship == "INVOLVES"


def test_graph_empty_by_default() -> None:
    """Graph should support empty initialization."""
    from sentinel.core.types import Graph

    graph = Graph(nodes=(), edges=())

    assert graph.nodes == (), f"Expected empty nodes tuple, got {graph.nodes}"
    assert graph.edges == (), f"Expected empty edges tuple, got {graph.edges}"


def test_scored_collision_dataclass_has_required_fields() -> None:
    """ScoredCollision should have path, confidence, and source_breakdown fields."""
    from sentinel.core.types import ScoredCollision

    collision = ScoredCollision(
        path=("Aunt Susan", "DRAINS", "LowEnergy", "CONFLICTS_WITH", "Presentation"),
        confidence=0.75,
        source_breakdown={"user_stated": 3, "ai_inferred": 2},
    )

    assert collision.path == (
        "Aunt Susan",
        "DRAINS",
        "LowEnergy",
        "CONFLICTS_WITH",
        "Presentation",
    ), f"Expected path, got {collision.path}"
    assert collision.confidence == 0.75, f"Expected confidence 0.75, got {collision.confidence}"
    assert collision.source_breakdown == {"user_stated": 3, "ai_inferred": 2}


def test_correction_dataclass_has_required_fields() -> None:
    """Correction should have node_id, action, and new_value fields."""
    from sentinel.core.types import Correction

    correction = Correction(
        node_id="node-1",
        action="delete",
        new_value=None,
    )

    assert correction.node_id == "node-1", f"Expected node_id 'node-1', got {correction.node_id}"
    assert correction.action == "delete", f"Expected action 'delete', got {correction.action}"
    assert correction.new_value is None, f"Expected new_value None, got {correction.new_value}"


def test_correction_with_modify_action() -> None:
    """Correction should support modify action with new_value."""
    from sentinel.core.types import Correction

    correction = Correction(
        node_id="node-1",
        action="modify",
        new_value="Updated Label",
    )

    assert correction.action == "modify"
    assert correction.new_value == "Updated Label"
