"""E2E Live tests for Epic 3: User Control & Trust.

These tests require a real LLM API key and make actual Cognee API calls.
Run with: uv run pytest -m live tests/live/test_epic3_user_control_e2e.py

Epic 3 Stories:
- Story 3.1: Delete AI-inferred nodes (covered in test_corrections_live.py)
- Story 3.2: Modify AI-inferred relationships
- Story 3.3: Acknowledge collision warnings
- Story 3.4: Suppress acknowledged warnings in check

CRITICAL: Per project-context.md, no LLM-integration story is "done"
without at least 1 passing @pytest.mark.live test.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Mark all tests in this module as live tests
pytestmark = pytest.mark.live


@pytest.fixture
def collision_scenario_text() -> str:
    """Schedule text designed to produce collision patterns."""
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


# =============================================================================
# Story 3.2: Modify AI-Inferred Relationships
# =============================================================================


@pytest.mark.asyncio
async def test_modify_edge_relationship_type_persists(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.2 AC #3: Edge modifications persist to corrections.json.

    E2E test:
    1. Ingest schedule via real Cognee API
    2. Find an edge to modify
    3. Modify its relationship type
    4. Reload graph
    5. Verify edge has new relationship type
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import CorrectionStore
    from sentinel.core.types import Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Step 1: Ingest schedule via real Cognee API
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)

        print(f"\nOriginal graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Step 2: Find an edge to modify (preferably DRAINS edge)
        drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]

        # Fallback to any edge if no DRAINS edges
        edges_to_choose = drains_edges if drains_edges else list(graph.edges)
        assert len(edges_to_choose) > 0, "Need at least one edge to test modification"

        edge_to_modify = edges_to_choose[0]
        original_relationship = edge_to_modify.relationship
        new_relationship = "ENERGIZES"  # Opposite of DRAINS

        print("\nEdge to modify:")
        print(f"  Source: {edge_to_modify.source_id}")
        print(f"  Target: {edge_to_modify.target_id}")
        print(f"  Original relationship: {original_relationship}")
        print(f"  New relationship: {new_relationship}")

        # Step 3: Apply modification
        correction = Correction(
            node_id=edge_to_modify.source_id,
            action="modify_relationship",
            new_value=new_relationship,
            target_node_id=edge_to_modify.target_id,
            edge_relationship=original_relationship,
        )

        mutated = engine.mutate(graph, correction)
        engine.persist(mutated)

        # Persist correction
        store = CorrectionStore()
        store.add_correction(correction, reason="Live test modification")

        # Step 4: Reload graph with corrections
        loaded = engine.load(apply_corrections=True)
        assert loaded is not None, "Should load graph"

        # Step 5: Verify edge has new relationship
        modified_edge = next(
            (
                e
                for e in loaded.edges
                if e.source_id == edge_to_modify.source_id
                and e.target_id == edge_to_modify.target_id
            ),
            None,
        )

        assert modified_edge is not None, (
            f"Modified edge should exist: {edge_to_modify.source_id} -> {edge_to_modify.target_id}"
        )
        assert modified_edge.relationship == new_relationship, (
            f"Edge relationship should be '{new_relationship}', got '{modified_edge.relationship}'"
        )

        print(f"\n✅ Edge relationship modified: {original_relationship} -> {new_relationship}")


@pytest.mark.asyncio
async def test_remove_edge_excludes_from_graph(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.2 AC #2: Remove edge without deleting nodes.

    E2E test:
    1. Ingest schedule via real Cognee API
    2. Find an edge to remove
    3. Remove it via corrections
    4. Reload graph
    5. Verify edge is gone but both nodes still exist
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import CorrectionStore
    from sentinel.core.types import Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Step 1: Ingest schedule
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)

        print(f"\nOriginal graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        assert len(graph.edges) > 0, "Need at least one edge to test removal"

        # Step 2: Find an edge to remove
        edge_to_remove = graph.edges[0]

        print("\nEdge to remove:")
        print(f"  Source: {edge_to_remove.source_id}")
        print(f"  Target: {edge_to_remove.target_id}")
        print(f"  Relationship: {edge_to_remove.relationship}")

        # Get nodes for later verification
        source_node = next((n for n in graph.nodes if n.id == edge_to_remove.source_id), None)
        target_node = next((n for n in graph.nodes if n.id == edge_to_remove.target_id), None)

        # Step 3: Remove edge
        correction = Correction(
            node_id=edge_to_remove.source_id,
            action="remove_edge",
            target_node_id=edge_to_remove.target_id,
            edge_relationship=edge_to_remove.relationship,
        )

        mutated = engine.mutate(graph, correction)
        engine.persist(mutated)

        store = CorrectionStore()
        store.add_correction(correction, reason="Live test edge removal")

        # Step 4: Reload graph
        loaded = engine.load(apply_corrections=True)
        assert loaded is not None

        # Step 5: Verify edge is removed
        matching_edge = next(
            (
                e
                for e in loaded.edges
                if e.source_id == edge_to_remove.source_id
                and e.target_id == edge_to_remove.target_id
                and e.relationship == edge_to_remove.relationship
            ),
            None,
        )

        assert matching_edge is None, (
            f"Edge should be removed: {edge_to_remove.source_id} --"
            f"[{edge_to_remove.relationship}]--> {edge_to_remove.target_id}"
        )

        # Verify nodes still exist
        loaded_node_ids = {n.id for n in loaded.nodes}
        if source_node:
            assert source_node.id in loaded_node_ids, (
                f"Source node '{source_node.label}' should still exist after edge removal"
            )
        if target_node:
            assert target_node.id in loaded_node_ids, (
                f"Target node '{target_node.label}' should still exist after edge removal"
            )

        print("\n✅ Edge removed, nodes preserved")
        print(f"  Remaining edges: {len(loaded.edges)}")


@pytest.mark.asyncio
async def test_multiple_edge_corrections_apply_in_order(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.2 AC #4: Corrections applied on graph load.

    E2E test:
    1. Ingest schedule via real Cognee API
    2. Apply multiple edge corrections (modify + remove)
    3. Reload graph
    4. Verify all corrections applied correctly
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import CorrectionStore
    from sentinel.core.types import Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)

        print(f"\nOriginal graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        if len(graph.edges) < 2:
            pytest.skip("Need at least 2 edges to test multiple corrections")

        store = CorrectionStore()
        corrections_applied = []

        # Apply modify to first edge
        edge1 = graph.edges[0]
        correction1 = Correction(
            node_id=edge1.source_id,
            action="modify_relationship",
            new_value="REQUIRES",
            target_node_id=edge1.target_id,
            edge_relationship=edge1.relationship,
        )
        graph = engine.mutate(graph, correction1)
        store.add_correction(correction1, reason="Multi-correction test - modify")
        corrections_applied.append(("modify", edge1.source_id, edge1.target_id))

        # Apply remove to second edge
        edge2 = graph.edges[1] if len(graph.edges) > 1 else None
        if edge2:
            correction2 = Correction(
                node_id=edge2.source_id,
                action="remove_edge",
                target_node_id=edge2.target_id,
                edge_relationship=edge2.relationship,
            )
            graph = engine.mutate(graph, correction2)
            store.add_correction(correction2, reason="Multi-correction test - remove")
            corrections_applied.append(("remove", edge2.source_id, edge2.target_id))

        engine.persist(graph)

        # Reload in new session
        new_engine = CogneeEngine()
        loaded = new_engine.load(apply_corrections=True)
        assert loaded is not None

        print(f"\nLoaded graph: {len(loaded.nodes)} nodes, {len(loaded.edges)} edges")

        # Verify modify correction
        modified_edge = next(
            (
                e
                for e in loaded.edges
                if e.source_id == edge1.source_id and e.target_id == edge1.target_id
            ),
            None,
        )
        if modified_edge:
            assert modified_edge.relationship == "REQUIRES", (
                f"Modified edge should have REQUIRES, got {modified_edge.relationship}"
            )
            print("  ✓ Edge modification applied")

        # Verify remove correction
        if edge2:
            removed_edge = next(
                (
                    e
                    for e in loaded.edges
                    if e.source_id == edge2.source_id
                    and e.target_id == edge2.target_id
                    and e.relationship == edge2.relationship
                ),
                None,
            )
            assert removed_edge is None, "Removed edge should not exist"
            print("  ✓ Edge removal applied")

        print("\n✅ Multiple corrections applied successfully")


# =============================================================================
# Story 3.3: Acknowledge Collision Warnings
# =============================================================================


@pytest.mark.asyncio
async def test_acknowledge_collision_persists(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.3 AC #3: Acknowledgment persists to acks.json.

    E2E test:
    1. Ingest schedule via real Cognee API
    2. Detect collisions
    3. Acknowledge a collision
    4. Reload acknowledgments
    5. Verify acknowledgment persisted
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import AcknowledgmentStore
    from sentinel.core.rules import detect_cross_domain_collisions, generate_collision_key
    from sentinel.core.types import Acknowledgment

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Step 1: Ingest schedule
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)
        engine.persist(graph)

        print(f"\nGraph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Step 2: Detect collisions
        collisions = detect_cross_domain_collisions(graph)
        print(f"Collisions detected: {len(collisions)}")

        if len(collisions) == 0:
            # If no collisions from real API, document and skip
            edge_types = {e.relationship for e in graph.edges}
            print(f"Edge types: {sorted(edge_types)}")
            pytest.skip(
                "No collisions detected from real Cognee API - "
                "LLM graph structure variance. This is expected behavior."
            )

        # Step 3: Acknowledge the first collision
        collision = collisions[0]
        collision_key = generate_collision_key(collision)
        first_node_label = collision.path[0]

        print("\nAcknowledging collision:")
        print(f"  Key: {collision_key}")
        print(f"  Path: {' -> '.join(collision.path)}")

        ack = Acknowledgment(
            collision_key=collision_key,
            node_label=first_node_label,
            path=collision.path,
        )

        store = AcknowledgmentStore()
        store.add_acknowledgment(ack)

        # Step 4: Verify persistence in new store instance
        new_store = AcknowledgmentStore()
        acked_keys = new_store.get_acknowledged_keys()

        assert collision_key in acked_keys, (
            f"Acknowledgment '{collision_key}' should persist. Found: {acked_keys}"
        )

        print(f"\n✅ Acknowledgment persisted: {collision_key}")


@pytest.mark.asyncio
async def test_remove_acknowledgment(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.3 AC #6: Remove acknowledgment via --remove flag.

    E2E test:
    1. Create and persist an acknowledgment
    2. Remove it
    3. Verify it's gone
    """
    from sentinel.core.persistence import AcknowledgmentStore
    from sentinel.core.types import Acknowledgment

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Create acknowledgment
        ack = Acknowledgment(
            collision_key="test-collision",
            node_label="Test Collision",
            path=("Test Node", "DRAINS", "Energy", "REQUIRES", "Focus"),
        )

        store = AcknowledgmentStore()
        store.add_acknowledgment(ack)

        # Verify it exists
        assert "test-collision" in store.get_acknowledged_keys()

        # Remove it
        store.remove_acknowledgment("test-collision")

        # Verify in new instance
        new_store = AcknowledgmentStore()
        assert "test-collision" not in new_store.get_acknowledged_keys(), (
            "Removed acknowledgment should not exist"
        )

        print("\n✅ Acknowledgment removed successfully")


# =============================================================================
# Story 3.4: Suppress Acknowledged Warnings in Check
# =============================================================================


@pytest.mark.asyncio
async def test_acknowledged_collision_hidden_in_check(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.4 AC #1 & #2: Acknowledged collisions hidden by default.

    E2E test:
    1. Ingest schedule, detect collisions
    2. Acknowledge all collisions
    3. Filter collisions (simulating check command)
    4. Verify no unacknowledged collisions remain
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import AcknowledgmentStore
    from sentinel.core.rules import detect_cross_domain_collisions, generate_collision_key
    from sentinel.core.types import Acknowledgment

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        # Step 1: Ingest and detect
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)
        engine.persist(graph)

        collisions = detect_cross_domain_collisions(graph)
        print(f"\nTotal collisions: {len(collisions)}")

        if len(collisions) == 0:
            pytest.skip(
                "No collisions detected from real Cognee API - LLM graph structure variance."
            )

        # Step 2: Acknowledge all collisions
        store = AcknowledgmentStore()
        for collision in collisions:
            key = generate_collision_key(collision)
            ack = Acknowledgment(
                collision_key=key,
                node_label=collision.path[0],
                path=collision.path,
            )
            store.add_acknowledgment(ack)
            print(f"  Acknowledged: {key}")

        # Step 3: Filter collisions (as check command does)
        acked_keys = store.get_acknowledged_keys()
        unacknowledged = [c for c in collisions if generate_collision_key(c) not in acked_keys]
        acknowledged = [c for c in collisions if generate_collision_key(c) in acked_keys]

        print(f"\nUnacknowledged: {len(unacknowledged)}")
        print(f"Acknowledged: {len(acknowledged)}")

        # Step 4: Verify
        assert len(unacknowledged) == 0, (
            f"All collisions should be acknowledged. "
            f"Unacknowledged: {[c.path for c in unacknowledged]}"
        )
        assert len(acknowledged) == len(collisions), "All collisions should be in acknowledged list"

        print(f"\n✅ All {len(collisions)} collisions acknowledged and would be hidden")


@pytest.mark.asyncio
async def test_show_acked_flag_displays_acknowledged(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Story 3.4 AC #3: --show-acked displays with [ACKED] label.

    E2E test:
    1. Ingest schedule, detect collisions
    2. Acknowledge a collision
    3. Simulate --show-acked behavior
    4. Verify collision still visible with acked status
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import AcknowledgmentStore
    from sentinel.core.rules import detect_cross_domain_collisions, generate_collision_key
    from sentinel.core.types import Acknowledgment

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)
        engine.persist(graph)

        collisions = detect_cross_domain_collisions(graph)

        if len(collisions) == 0:
            pytest.skip(
                "No collisions detected from real Cognee API - LLM graph structure variance."
            )

        # Acknowledge first collision only
        first_collision = collisions[0]
        key = generate_collision_key(first_collision)

        store = AcknowledgmentStore()
        ack = Acknowledgment(
            collision_key=key,
            node_label=first_collision.path[0],
            path=first_collision.path,
        )
        store.add_acknowledgment(ack)

        # Simulate --show-acked: display all collisions with status
        acked_keys = store.get_acknowledged_keys()

        displayed_collisions = []
        for collision in collisions:
            ckey = generate_collision_key(collision)
            is_acked = ckey in acked_keys
            displayed_collisions.append(
                {
                    "collision": collision,
                    "key": ckey,
                    "is_acknowledged": is_acked,
                    "label": "[ACKED]" if is_acked else "",
                }
            )

        print("\nWith --show-acked:")
        for item in displayed_collisions:
            status = item["label"] or "[NEW]"
            print(f"  {status} {' -> '.join(item['collision'].path)}")

        # Verify acknowledged collision is marked
        acked_items = [d for d in displayed_collisions if d["is_acknowledged"]]
        assert len(acked_items) >= 1, "At least one collision should be marked as acknowledged"
        assert acked_items[0]["label"] == "[ACKED]", (
            "Acknowledged collision should have [ACKED] label"
        )

        print("\n✅ --show-acked correctly displays acknowledged collision with label")


# =============================================================================
# Full E2E User Journey Tests
# =============================================================================


@pytest.mark.asyncio
async def test_full_user_journey_delete_ack_check(
    collision_scenario_text: str,
    tmp_path: Path,
) -> None:
    """Full E2E: User deletes node, acknowledges remaining, runs check.

    Complete user journey:
    1. Ingest schedule
    2. Delete an AI-inferred node
    3. Acknowledge remaining collision
    4. Run check (should show no new warnings)
    """
    from sentinel.core.engine import CogneeEngine
    from sentinel.core.persistence import AcknowledgmentStore, CorrectionStore
    from sentinel.core.rules import detect_cross_domain_collisions, generate_collision_key
    from sentinel.core.types import Acknowledgment, Correction

    custom_xdg = str(tmp_path)

    with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
        print("\n=== STEP 1: Ingest Schedule ===")
        engine = CogneeEngine()
        graph = await engine.ingest(collision_scenario_text)
        engine.persist(graph)

        print(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        initial_collisions = detect_cross_domain_collisions(graph)
        print(f"Initial collisions: {len(initial_collisions)}")

        if len(initial_collisions) == 0:
            pytest.skip("No collisions detected - LLM variance")

        print("\n=== STEP 2: Delete AI-Inferred Node ===")
        ai_nodes = [n for n in graph.nodes if n.source == "ai-inferred"]
        if ai_nodes:
            node_to_delete = ai_nodes[0]
            correction = Correction(node_id=node_to_delete.id, action="delete")
            graph = engine.mutate(graph, correction)
            engine.persist(graph)

            correction_store = CorrectionStore()
            correction_store.add_correction(correction, reason="User journey test")
            print(f"Deleted: {node_to_delete.label}")

        print("\n=== STEP 3: Acknowledge Remaining Collisions ===")
        # Re-detect collisions after deletion
        remaining_collisions = detect_cross_domain_collisions(graph)
        print(f"Remaining collisions: {len(remaining_collisions)}")

        ack_store = AcknowledgmentStore()
        for collision in remaining_collisions:
            key = generate_collision_key(collision)
            ack = Acknowledgment(
                collision_key=key,
                node_label=collision.path[0],
                path=collision.path,
            )
            ack_store.add_acknowledgment(ack)
            print(f"Acknowledged: {key}")

        print("\n=== STEP 4: Check (should show no new warnings) ===")
        # Simulate check command behavior
        acked_keys = ack_store.get_acknowledged_keys()
        unacknowledged = [
            c for c in remaining_collisions if generate_collision_key(c) not in acked_keys
        ]

        print(f"Unacknowledged collisions: {len(unacknowledged)}")

        # In actual check command, exit code would be 0 if no unacknowledged
        expected_exit_code = 0 if len(unacknowledged) == 0 else 1

        assert expected_exit_code == 0, (
            f"Expected clean check (exit 0), but found {len(unacknowledged)} "
            f"unacknowledged collisions"
        )

        print("\n✅ Full user journey complete: No new collision warnings!")
