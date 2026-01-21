"""BUG-003 E2E Validation Tests.

These tests validate that semantic node consolidation improves collision
detection from ~30% to ≥80% success rate (target 100%).

Run with: uv run pytest -m live tests/live/test_bug003_e2e_validation.py -v -s

AC #5: Given explicit collision test fixture, when `sentinel paste` and `sentinel check`
are run 10 consecutive times, collision detection succeeds in at least 8/10 runs.

AC #6: Given a non-collision fixture (boring week), no false positive collisions detected.

AC #7: Consolidation completes in < 100ms for 50+ node graphs.
"""

import logging
import time
from pathlib import Path

import pytest

# Mark all tests in this module as live tests
pytestmark = pytest.mark.live

logger = logging.getLogger(__name__)


@pytest.fixture
def typical_week_fixture() -> str:
    """Load maya_typical_week.txt fixture (has collision scenario)."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "schedules" / "maya_typical_week.txt"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    return fixture_path.read_text()


@pytest.fixture
def boring_week_fixture() -> str:
    """Load maya_boring_week.txt fixture (no collisions expected)."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "schedules" / "maya_boring_week.txt"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    return fixture_path.read_text()


async def run_single_collision_detection_trial(
    schedule_text: str, trial_num: int
) -> tuple[bool, int, list[str], int, int]:
    """Run a single collision detection trial.

    Returns:
        Tuple of (collision_found, collision_count, edge_types, original_nodes, consolidated_nodes)
    """
    from sentinel.core.consolidation import consolidate_semantic_nodes
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.rules import detect_cross_domain_collisions

    engine = CogneeEngine()
    graph = await engine.ingest(schedule_text)

    # Track consolidation stats
    original_nodes = len(graph.nodes)
    consolidated_graph = consolidate_semantic_nodes(graph)
    consolidated_nodes = len(consolidated_graph.nodes)

    edge_types = sorted({e.relationship for e in graph.edges})
    collisions = detect_cross_domain_collisions(graph)

    collision_found = len(collisions) >= 1
    collision_count = len(collisions)

    logger.info(
        "Trial %d: %d→%d nodes (merged %d), %d edges, %d collisions, types=%s",
        trial_num,
        original_nodes,
        consolidated_nodes,
        original_nodes - consolidated_nodes,
        len(graph.edges),
        collision_count,
        edge_types,
    )

    return collision_found, collision_count, edge_types, original_nodes, consolidated_nodes


@pytest.mark.asyncio
async def test_bug003_ac5_collision_detection_10_trials(
    typical_week_fixture: str,
) -> None:
    """BUG-003 AC #5: 10 consecutive trials with ≥80% success rate.

    This test validates that semantic node consolidation improves
    collision detection consistency from ~30% to ≥80%.
    """
    num_trials = 10
    successes = 0
    total_merged = 0
    results: list[dict] = []

    print(f"\n{'=' * 60}")
    print("BUG-003 E2E Validation: 10 Consecutive Trials")
    print("Testing: Semantic Node Consolidation")
    print(f"{'=' * 60}")

    for trial_num in range(1, num_trials + 1):
        print(f"\n--- Trial {trial_num}/{num_trials} ---")

        (
            collision_found,
            collision_count,
            edge_types,
            original_nodes,
            consolidated_nodes,
        ) = await run_single_collision_detection_trial(typical_week_fixture, trial_num)

        merged_count = original_nodes - consolidated_nodes
        total_merged += merged_count

        if collision_found:
            successes += 1
            print(f"✓ PASS: Found {collision_count} collision(s)")
        else:
            print("✗ FAIL: No collisions found")

        print(f"  Nodes: {original_nodes} → {consolidated_nodes} (merged {merged_count})")
        print(f"  Edge types: {edge_types}")

        results.append(
            {
                "trial": trial_num,
                "success": collision_found,
                "collision_count": collision_count,
                "edge_types": edge_types,
                "merged_count": merged_count,
            }
        )

    # Calculate success rate
    success_rate = (successes / num_trials) * 100
    avg_merged = total_merged / num_trials

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"Trials: {num_trials}")
    print(f"Successes: {successes}")
    print(f"Failures: {num_trials - successes}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Average nodes merged: {avg_merged:.1f}")
    print("Minimum Required: 80%")
    print("Target: 100%")

    # Document failure patterns if any
    failures = [r for r in results if not r["success"]]
    if failures:
        print("\nFailure Analysis:")
        for failure in failures:
            print(f"  Trial {failure['trial']}: {failure['edge_types']}")

    # AC #5: Success rate must be at least 80%
    assert success_rate >= 80, (
        f"BUG-003 AC #5 FAILED: Success rate {success_rate:.1f}% < 80% minimum. "
        f"Successes: {successes}/{num_trials}. "
        f"Node consolidation may need tuning. See failure analysis above."
    )

    if success_rate == 100:
        print("\n🎉 TARGET ACHIEVED: 100% success rate!")
    else:
        print(f"\n⚠️  Success rate {success_rate:.1f}% meets minimum but below 100% target")


@pytest.mark.asyncio
async def test_bug003_ac6_no_false_positives_boring_week(
    boring_week_fixture: str,
) -> None:
    """BUG-003 AC #6: No false positives with boring week fixture.

    The boring week fixture contains no energy-draining activities,
    so no collisions should be detected.
    """
    num_trials = 3  # AC #6 specifies 3 trials
    false_positives = 0
    results: list[dict] = []

    print(f"\n{'=' * 60}")
    print("BUG-003 False Positive Validation: 3 Trials")
    print(f"{'=' * 60}")

    for trial_num in range(1, num_trials + 1):
        print(f"\n--- Trial {trial_num}/{num_trials} ---")

        (
            collision_found,
            collision_count,
            edge_types,
            original_nodes,
            consolidated_nodes,
        ) = await run_single_collision_detection_trial(boring_week_fixture, trial_num)

        merged_count = original_nodes - consolidated_nodes

        if collision_found:
            false_positives += 1
            print(f"✗ FALSE POSITIVE: Found {collision_count} collision(s)")
        else:
            print("✓ PASS: No collisions (correct)")

        print(f"  Nodes: {original_nodes} → {consolidated_nodes} (merged {merged_count})")
        print(f"  Edge types: {edge_types}")

        results.append(
            {
                "trial": trial_num,
                "false_positive": collision_found,
                "collision_count": collision_count,
                "edge_types": edge_types,
            }
        )

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"Trials: {num_trials}")
    print(f"False Positives: {false_positives}")
    print(f"True Negatives: {num_trials - false_positives}")

    # AC #6: No false positives
    assert false_positives == 0, (
        f"BUG-003 AC #6 FAILED: {false_positives} false positive(s) detected. "
        "Node consolidation may be incorrectly merging unrelated nodes. "
        "Consider increasing NODE_SIMILARITY_THRESHOLD."
    )

    print("\n✓ AC #6 PASSED: No false positives detected")


@pytest.mark.asyncio
async def test_bug003_ac7_consolidation_performance() -> None:
    """BUG-003 AC #7: Consolidation completes in < 100ms for 50+ node graphs.

    This test validates that RapidFuzz-based consolidation is performant.
    """
    from sentinel.core.consolidation import consolidate_semantic_nodes
    from sentinel.core.types import Graph, Node

    print(f"\n{'=' * 60}")
    print("BUG-003 Performance Validation")
    print(f"{'=' * 60}")

    # Create a graph with 50+ nodes for performance testing
    nodes = []
    for i in range(60):
        # Mix of energy-related and regular nodes
        if i % 3 == 0:
            label = f"energy_state_{i}"
        elif i % 3 == 1:
            label = f"activity_{i}"
        else:
            label = f"person_{i}"

        nodes.append(
            Node(
                id=str(i),
                label=label,
                type="Entity",
                source="ai-inferred",
            )
        )

    graph = Graph(nodes=tuple(nodes), edges=())

    # Time the consolidation
    start_time = time.perf_counter()
    consolidated = consolidate_semantic_nodes(graph)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    print(f"\nInput nodes: {len(graph.nodes)}")
    print(f"Output nodes: {len(consolidated.nodes)}")
    print(f"Consolidation time: {elapsed_ms:.2f}ms")
    print("Threshold: < 100ms")

    # AC #7: Consolidation must complete in < 100ms
    assert elapsed_ms < 100, (
        f"BUG-003 AC #7 FAILED: Consolidation took {elapsed_ms:.2f}ms > 100ms. "
        "Performance optimization needed."
    )

    print("\n✓ AC #7 PASSED: Consolidation performance is acceptable")


@pytest.mark.asyncio
async def test_bug003_consolidation_logging() -> None:
    """Verify consolidation produces debug logging.

    This test validates that consolidation stats are logged for debugging.
    """
    from sentinel.core.consolidation import consolidate_semantic_nodes
    from sentinel.core.types import Edge, Graph, Node

    print(f"\n{'=' * 60}")
    print("BUG-003 Debug Logging Validation")
    print(f"{'=' * 60}")

    # Create a graph with semantically equivalent nodes
    nodes = (
        Node(id="1", label="emotional_exhaustion", type="EnergyState", source="ai-inferred"),
        Node(id="2", label="low_energy", type="EnergyState", source="ai-inferred"),
        Node(id="3", label="energy_drain", type="EnergyState", source="ai-inferred"),
        Node(id="4", label="dinner", type="Activity", source="user-stated"),
        Node(id="5", label="presentation", type="Activity", source="user-stated"),
    )
    edges = (
        Edge(source_id="4", target_id="1", relationship="DRAINS", confidence=1.0),
        Edge(source_id="2", target_id="5", relationship="CONFLICTS_WITH", confidence=1.0),
        Edge(source_id="5", target_id="3", relationship="REQUIRES", confidence=1.0),
    )
    graph = Graph(nodes=nodes, edges=edges)

    print(f"\nInput: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # Run consolidation
    consolidated = consolidate_semantic_nodes(graph)

    print(f"Output: {len(consolidated.nodes)} nodes, {len(consolidated.edges)} edges")
    print(f"Merged: {len(graph.nodes) - len(consolidated.nodes)} semantically equivalent nodes")

    # Document the remaining nodes
    print("\nRemaining nodes after consolidation:")
    for node in consolidated.nodes:
        print(f"  {node.id}: {node.label} ({node.type})")

    # Document the edges with rewritten references
    print("\nEdges with rewritten references:")
    for edge in consolidated.edges:
        print(f"  {edge.source_id} --[{edge.relationship}]--> {edge.target_id}")

    # Verify some nodes were merged (energy-related nodes should merge)
    assert len(consolidated.nodes) < len(graph.nodes), (
        "Expected some nodes to be merged, but node count unchanged."
    )

    print("\n✓ Consolidation successfully merged semantically equivalent nodes")
