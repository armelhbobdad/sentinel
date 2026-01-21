"""Live tests for corrections feature (Story 3.1 Task 6.5).

These tests require a real LLM API key and make actual Cognee API calls.
Run with: uv run pytest -m live tests/live/test_corrections_live.py

Validates AC #5: Deleted nodes don't appear in check results.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Mark all tests in this module as live tests
pytestmark = pytest.mark.live


@pytest.fixture
def collision_scenario_text() -> str:
    """Schedule text designed to produce collision patterns with deletable nodes."""
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
    """


@pytest.mark.asyncio
async def test_deleted_node_excluded_from_collision_paths(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Verify deleted AI-inferred nodes don't appear in check collision results.

    Story 3.1 AC #5: When I run `sentinel check`, previously deleted nodes
    no longer appear in collision paths.

    This live test:
    1. Ingests a collision-inducing schedule via Cognee API
    2. Identifies an AI-inferred EnergyState node (e.g., "drained")
    3. Deletes it via corrections
    4. Runs collision detection
    5. Verifies the deleted node doesn't appear in results
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import CorrectionStore
    from sentinel.core.rules import detect_cross_domain_collisions
    from sentinel.core.types import Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Step 1: Ingest schedule via real Cognee API
        engine = CogneeEngine()
        original_graph = await engine.ingest(collision_scenario_text)

        # Document what we got
        node_count = len(original_graph.nodes)
        edge_count = len(original_graph.edges)
        print(f"\nOriginal graph: {node_count} nodes, {edge_count} edges")
        for node in original_graph.nodes:
            print(f"  Node: {node.label} ({node.type}, {node.source})")

        # Step 2: Find AI-inferred nodes (candidates for deletion)
        ai_inferred_nodes = [n for n in original_graph.nodes if n.source == "ai-inferred"]
        print(f"\nAI-inferred nodes: {len(ai_inferred_nodes)}")
        for node in ai_inferred_nodes:
            print(f"  {node.id}: {node.label}")

        assert len(ai_inferred_nodes) > 0, (
            "Expected at least one AI-inferred node for deletion test"
        )

        # Step 3: Persist original graph and find collisions
        engine.persist(original_graph)

        original_collisions = detect_cross_domain_collisions(original_graph)
        print(f"\nOriginal collisions: {len(original_collisions)}")
        for c in original_collisions:
            print(f"  Path: {' -> '.join(c.path)}")

        # Step 4: Delete an AI-inferred node that might be part of collision
        # Prefer EnergyState nodes as they're typically part of collision paths
        energy_states = [n for n in ai_inferred_nodes if n.type == "EnergyState"]
        node_to_delete = energy_states[0] if energy_states else ai_inferred_nodes[0]
        print(f"\nDeleting node: {node_to_delete.id} ({node_to_delete.label})")

        # Apply correction
        correction = Correction(node_id=node_to_delete.id, action="delete")
        mutated_graph = engine.mutate(original_graph, correction)

        # Persist correction
        store = CorrectionStore()
        store.add_correction(correction, reason="Live test deletion")

        # Persist mutated graph
        engine.persist(mutated_graph)

        # Step 5: Load graph with corrections applied
        loaded_graph = engine.load(apply_corrections=True)
        assert loaded_graph is not None, "Should load graph"

        # Step 6: Verify deleted node is NOT in loaded graph
        loaded_node_ids = {n.id for n in loaded_graph.nodes}
        assert node_to_delete.id not in loaded_node_ids, (
            f"Deleted node {node_to_delete.id} should not be in loaded graph"
        )

        # Step 7: Run collision detection on corrected graph
        corrected_collisions = detect_cross_domain_collisions(loaded_graph)
        print(f"\nCorrected collisions: {len(corrected_collisions)}")
        for c in corrected_collisions:
            print(f"  Path: {' -> '.join(c.path)}")

        # Step 8: Verify deleted node doesn't appear in any collision path
        deleted_label = node_to_delete.label
        for collision in corrected_collisions:
            path_str = " ".join(collision.path)
            assert deleted_label not in path_str, (
                f"Deleted node label '{deleted_label}' should not appear in "
                f"collision path: {collision.path}"
            )

        print(f"\n✅ Deleted node '{deleted_label}' correctly excluded from collision detection")


@pytest.mark.asyncio
async def test_correction_persists_across_load_cycles(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Verify corrections persist and are applied across multiple load cycles.

    Story 3.1 AC #4: Corrections are persisted immediately.
    Story 3.1 AC #5: Deleted nodes filtered on subsequent loads.
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import CorrectionStore
    from sentinel.core.types import Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Ingest and persist
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)
        engine.persist(graph)

        # Find and delete an AI-inferred node
        ai_nodes = [n for n in graph.nodes if n.source == "ai-inferred"]
        assert len(ai_nodes) > 0, "Need AI-inferred nodes for test"

        node_to_delete = ai_nodes[0]
        correction = Correction(node_id=node_to_delete.id, action="delete")

        # Apply mutation and persist
        mutated = engine.mutate(graph, correction)
        engine.persist(mutated)

        store = CorrectionStore()
        store.add_correction(correction, reason="Persistence test")

        # Create NEW engine instance (simulating new session)
        new_engine = CogneeEngine()
        loaded = new_engine.load(apply_corrections=True)

        assert loaded is not None
        loaded_ids = {n.id for n in loaded.nodes}
        assert node_to_delete.id not in loaded_ids, (
            "Correction should persist across engine instances"
        )

        # Verify correction file exists and has correct content
        new_store = CorrectionStore()
        deleted_ids = new_store.get_deleted_node_ids()
        assert node_to_delete.id in deleted_ids, (
            "Correction should be retrievable from new store instance"
        )

        print(f"\n✅ Correction for '{node_to_delete.label}' persists across sessions")
