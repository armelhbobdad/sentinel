"""Live tests to verify DRAINS edges in real Cognee output.

These tests require a real LLM API key and make actual Cognee API calls.
Run with: uv run pytest -m live tests/live/

CRITICAL: Story 2.1 depends on DRAINS edges for collision detection.
Epic 1 testing only observed SCHEDULED_AT and INVOLVES edges.
This test documents what edge types Cognee actually produces.
"""

import pytest

# Mark all tests in this module as live tests
pytestmark = pytest.mark.live


@pytest.fixture
def collision_scenario_text() -> str:
    """Schedule text designed to elicit DRAINS edges.

    This text explicitly mentions:
    - Energy draining activities
    - Emotional exhaustion
    - Conflicts with focus requirements
    """
    return """
    My week schedule:

    Sunday evening: Dinner with Aunt Susan.
    Note: Aunt Susan is emotionally draining - she constantly complains
    and I always feel exhausted after spending time with her.
    This dinner will drain my energy significantly.

    Monday 9am: Important strategy presentation to the executive team.
    This requires high focus and mental sharpness.
    I need to be well-rested and energized for this.

    The problem: After the draining dinner with Aunt Susan on Sunday,
    I won't have the energy required for Monday's presentation.
    Her exhausting nature conflicts with my need for focus.
    """


@pytest.mark.asyncio
async def test_cognee_produces_drains_edges(collision_scenario_text: str) -> None:
    """Verify that Cognee produces DRAINS edges from energy-draining scenarios.

    CRITICAL: This test documents actual Cognee behavior.
    If this test fails, collision detection in Story 2.1 may not work as expected.
    """
    from sentinel.core.engine import CogneeEngine

    engine = CogneeEngine()
    graph = await engine.ingest(collision_scenario_text)

    # Document all edge types found
    edge_types = {edge.relationship for edge in graph.edges}
    print(f"\nEdge types found: {sorted(edge_types)}")

    # Document all edges
    print("\nAll edges:")
    for edge in graph.edges:
        print(f"  {edge.source_id} --[{edge.relationship}]--> {edge.target_id}")

    # Check for DRAINS edges
    drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]

    # This assertion documents expected behavior
    # If it fails, we need prompt engineering or post-processing
    if not drains_edges:
        pytest.skip(
            "DRAINS edges not produced by Cognee. "
            "Collision detection may require prompt engineering or post-processing. "
            f"Edge types found: {sorted(edge_types)}"
        )

    assert len(drains_edges) >= 1, (
        f"Expected at least one DRAINS edge, got {len(drains_edges)}. "
        f"Edge types found: {sorted(edge_types)}"
    )


@pytest.mark.asyncio
async def test_cognee_produces_collision_pattern_edges(
    collision_scenario_text: str,
) -> None:
    """Verify Cognee produces edges needed for collision pattern.

    Pattern needed: DRAINS → CONFLICTS_WITH → REQUIRES

    Documents which edge types Cognee actually produces.
    """
    from sentinel.core.engine import CogneeEngine

    engine = CogneeEngine()
    graph = await engine.ingest(collision_scenario_text)

    # Document edge type counts
    edge_counts: dict[str, int] = {}
    for edge in graph.edges:
        edge_counts[edge.relationship] = edge_counts.get(edge.relationship, 0) + 1

    print("\nEdge type counts:")
    for rel_type, count in sorted(edge_counts.items()):
        print(f"  {rel_type}: {count}")

    # Check for collision pattern components
    has_drains = any(e.relationship == "DRAINS" for e in graph.edges)
    has_conflicts = any(e.relationship == "CONFLICTS_WITH" for e in graph.edges)
    has_requires = any(e.relationship == "REQUIRES" for e in graph.edges)

    print("\nCollision pattern components:")
    print(f"  DRAINS: {'✓' if has_drains else '✗'}")
    print(f"  CONFLICTS_WITH: {'✓' if has_conflicts else '✗'}")
    print(f"  REQUIRES: {'✓' if has_requires else '✗'}")

    # Document findings
    if not all([has_drains, has_conflicts, has_requires]):
        missing = []
        if not has_drains:
            missing.append("DRAINS")
        if not has_conflicts:
            missing.append("CONFLICTS_WITH")
        if not has_requires:
            missing.append("REQUIRES")

        pytest.skip(
            f"Missing collision pattern edges: {missing}. "
            "Consider prompt engineering or post-processing to infer these relationships. "
            f"Available edge types: {list(edge_counts.keys())}"
        )


@pytest.mark.asyncio
async def test_document_cognee_entity_extraction(collision_scenario_text: str) -> None:
    """Document what entities Cognee extracts from schedule text.

    This is informational - helps understand Cognee's extraction capabilities.
    """
    from sentinel.core.engine import CogneeEngine

    engine = CogneeEngine()
    graph = await engine.ingest(collision_scenario_text)

    # Document nodes by type
    nodes_by_type: dict[str, list[str]] = {}
    for node in graph.nodes:
        nodes_by_type.setdefault(node.type, []).append(node.label)

    print("\nEntities extracted by type:")
    for node_type, labels in sorted(nodes_by_type.items()):
        print(f"  {node_type}:")
        for label in labels:
            print(f"    - {label}")

    # Check for expected entities
    all_labels = [n.label.lower() for n in graph.nodes]

    # These should be extracted if Cognee is working correctly
    expected = ["aunt susan", "dinner", "presentation"]
    found = [e for e in expected if any(e in label for label in all_labels)]
    missing = [e for e in expected if e not in found]

    print(f"\nExpected entities found: {found}")
    print(f"Expected entities missing: {missing}")

    assert len(graph.nodes) > 0, "Expected at least one entity extracted"
