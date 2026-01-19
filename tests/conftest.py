"""Pytest configuration and shared fixtures.

This module contains the MockEngine implementation and fixtures
for testing Sentinel without requiring LLM calls.
"""

from pathlib import Path

import pytest

from sentinel.core.engine import Subgraph
from sentinel.core.types import Correction, Edge, Graph, Node, ScoredCollision

# Fixture directory path
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "schedules"


class MockEngine:
    """Mock implementation of GraphEngine for deterministic testing.

    This engine produces consistent, predictable graphs from text input,
    enabling tests to run without LLM calls while still exercising
    the collision detection logic.
    """

    def __init__(self) -> None:
        """Initialize MockEngine with empty state."""
        self._stored_graph: Graph | None = None

    async def ingest(self, text: str) -> Graph:
        """Create a deterministic graph from text.

        Uses text content to determine which fixture scenario to produce.
        Same input always produces same output.

        Args:
            text: Schedule text to parse.

        Returns:
            Deterministic Graph based on text content.
        """
        # Determine scenario based on text content
        text_lower = text.lower()

        if "aunt susan" in text_lower or "emotionally draining" in text_lower:
            return self._create_collision_graph(text)
        elif any(c in text for c in ["☕", "María", "über", "日本語"]):
            return self._create_unicode_graph(text)
        else:
            return self._create_boring_graph(text)

    def _create_collision_graph(self, text: str) -> Graph:
        """Create a graph with collision scenario (typical week)."""
        nodes = [
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
                metadata={"extracted_from": "Sunday dinner"},
            ),
            Node(
                id="activity-dinner",
                label="Dinner with Aunt Susan",
                type="Activity",
                source="user-stated",
                metadata={"day": "Sunday"},
            ),
            Node(
                id="energy-low",
                label="Low Energy",
                type="EnergyState",
                source="ai-inferred",
                metadata={"level": "depleted"},
            ),
            Node(
                id="energy-high",
                label="High Focus Required",
                type="EnergyState",
                source="ai-inferred",
                metadata={"level": "peak"},
            ),
            Node(
                id="activity-presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
                metadata={"day": "Monday"},
            ),
            Node(
                id="timeslot-sunday-evening",
                label="Sunday Evening",
                type="TimeSlot",
                source="ai-inferred",
                metadata={"day": "Sunday", "time": "evening"},
            ),
            Node(
                id="timeslot-monday-morning",
                label="Monday Morning",
                type="TimeSlot",
                source="ai-inferred",
                metadata={"day": "Monday", "time": "morning"},
            ),
        ]

        # Include boundary confidence values for testing thresholds
        edges = [
            Edge(
                source_id="person-aunt-susan",
                target_id="energy-low",
                relationship="DRAINS",
                confidence=0.81,  # Boundary: just above HIGH_CONFIDENCE
                metadata={"reason": "emotionally draining"},
            ),
            Edge(
                source_id="activity-dinner",
                target_id="person-aunt-susan",
                relationship="INVOLVES",
                confidence=0.80,  # Boundary: exactly HIGH_CONFIDENCE
                metadata={},
            ),
            Edge(
                source_id="energy-low",
                target_id="energy-high",
                relationship="CONFLICTS_WITH",
                confidence=0.79,  # Boundary: just below HIGH_CONFIDENCE
                metadata={"conflict_type": "energy_depletion"},
            ),
            Edge(
                source_id="activity-presentation",
                target_id="energy-high",
                relationship="REQUIRES",
                confidence=0.51,  # Boundary: just above MEDIUM_CONFIDENCE
                metadata={"requirement": "mental_sharpness"},
            ),
            Edge(
                source_id="activity-dinner",
                target_id="timeslot-sunday-evening",
                relationship="SCHEDULED_AT",
                confidence=0.50,  # Boundary: exactly MEDIUM_CONFIDENCE
                metadata={},
            ),
            Edge(
                source_id="activity-presentation",
                target_id="timeslot-monday-morning",
                relationship="SCHEDULED_AT",
                confidence=0.49,  # Boundary: just below MEDIUM_CONFIDENCE
                metadata={},
            ),
        ]

        return Graph(nodes=nodes, edges=edges)

    def _create_boring_graph(self, text: str) -> Graph:
        """Create a graph without collision scenario (boring week)."""
        nodes = [
            Node(
                id="activity-standup",
                label="Regular Standup",
                type="Activity",
                source="user-stated",
                metadata={"day": "Monday"},
            ),
            Node(
                id="activity-docs",
                label="Documentation Updates",
                type="Activity",
                source="user-stated",
                metadata={"day": "Tuesday"},
            ),
            Node(
                id="activity-lunch",
                label="Team Lunch",
                type="Activity",
                source="user-stated",
                metadata={"day": "Wednesday"},
            ),
            Node(
                id="timeslot-monday",
                label="Monday",
                type="TimeSlot",
                source="ai-inferred",
                metadata={"day": "Monday"},
            ),
            Node(
                id="timeslot-tuesday",
                label="Tuesday",
                type="TimeSlot",
                source="ai-inferred",
                metadata={"day": "Tuesday"},
            ),
            Node(
                id="timeslot-wednesday",
                label="Wednesday",
                type="TimeSlot",
                source="ai-inferred",
                metadata={"day": "Wednesday"},
            ),
        ]

        # No DRAINS relationships - just scheduling
        edges = [
            Edge(
                source_id="activity-standup",
                target_id="timeslot-monday",
                relationship="SCHEDULED_AT",
                confidence=0.90,
                metadata={},
            ),
            Edge(
                source_id="activity-docs",
                target_id="timeslot-tuesday",
                relationship="SCHEDULED_AT",
                confidence=0.90,
                metadata={},
            ),
            Edge(
                source_id="activity-lunch",
                target_id="timeslot-wednesday",
                relationship="SCHEDULED_AT",
                confidence=0.90,
                metadata={},
            ),
        ]

        return Graph(nodes=nodes, edges=edges)

    def _create_unicode_graph(self, text: str) -> Graph:
        """Create a graph preserving Unicode characters (edge cases)."""
        nodes = [
            Node(
                id="person-maria",
                label="María ☕",
                type="Person",
                source="user-stated",
                metadata={"extracted_from": "coffee meeting"},
            ),
            Node(
                id="person-jean-pierre",
                label="Jean-Pierre",
                type="Person",
                source="user-stated",
                metadata={"extracted_from": "über-important project"},
            ),
            Node(
                id="activity-coffee",
                label="Coffee with María ☕",
                type="Activity",
                source="user-stated",
                metadata={"day": "Monday"},
            ),
            Node(
                id="activity-meeting",
                label="über-important project meeting",
                type="Activity",
                source="user-stated",
                metadata={"day": "Tuesday"},
            ),
            Node(
                id="activity-japanese",
                label="日本語テスト",
                type="Activity",
                source="user-stated",
                metadata={"day": "Wednesday"},
            ),
        ]

        edges = [
            Edge(
                source_id="activity-coffee",
                target_id="person-maria",
                relationship="INVOLVES",
                confidence=0.85,
                metadata={},
            ),
            Edge(
                source_id="activity-meeting",
                target_id="person-jean-pierre",
                relationship="INVOLVES",
                confidence=0.85,
                metadata={},
            ),
        ]

        return Graph(nodes=nodes, edges=edges)

    async def query_collisions(self, graph: Graph) -> list[ScoredCollision]:
        """Detect collisions in the graph.

        For MockEngine, checks for DRAINS -> CONFLICTS_WITH -> REQUIRES pattern.

        Args:
            graph: The graph to analyze.

        Returns:
            List of detected collisions.
        """
        collisions: list[ScoredCollision] = []

        # Look for DRAINS edges (indicating energy drain)
        drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]

        if not drains_edges:
            return collisions

        # Build collision path
        for drain_edge in drains_edges:
            # Find connected CONFLICTS_WITH edge
            conflicts = [
                e
                for e in graph.edges
                if e.relationship == "CONFLICTS_WITH" and e.source_id == drain_edge.target_id
            ]

            for conflict_edge in conflicts:
                # Find REQUIRES edge pointing to the conflicting state
                requires = [
                    e
                    for e in graph.edges
                    if e.relationship == "REQUIRES" and e.target_id == conflict_edge.target_id
                ]

                for requires_edge in requires:
                    # Build path labels
                    source_node = next(
                        (n for n in graph.nodes if n.id == drain_edge.source_id), None
                    )
                    target_node = next(
                        (n for n in graph.nodes if n.id == requires_edge.source_id), None
                    )

                    if source_node and target_node:
                        path = [
                            source_node.label,
                            "DRAINS",
                            next(
                                (n.label for n in graph.nodes if n.id == drain_edge.target_id),
                                "?",
                            ),
                            "CONFLICTS_WITH",
                            next(
                                (n.label for n in graph.nodes if n.id == conflict_edge.target_id),
                                "?",
                            ),
                            "REQUIRES",
                            target_node.label,
                        ]

                        # Calculate confidence from edge confidences
                        avg_confidence = (
                            drain_edge.confidence
                            + conflict_edge.confidence
                            + requires_edge.confidence
                        ) / 3

                        # Determine source breakdown
                        path_nodes = [source_node, target_node]
                        user_stated = sum(1 for n in path_nodes if n.source == "user-stated")
                        ai_inferred = sum(1 for n in path_nodes if n.source == "ai-inferred")
                        total = user_stated + ai_inferred

                        source_breakdown = {
                            "user-stated": user_stated / total if total > 0 else 0.0,
                            "ai-inferred": ai_inferred / total if total > 0 else 0.0,
                        }

                        collisions.append(
                            ScoredCollision(
                                path=path,
                                confidence=round(avg_confidence, 2),
                                source_breakdown=source_breakdown,
                            )
                        )

        return collisions

    async def get_neighbors(self, node_id: str, depth: int = 2) -> Subgraph:
        """Get neighbors of a node (stub implementation).

        Args:
            node_id: ID of the node to explore from.
            depth: Maximum depth to traverse.

        Returns:
            Subgraph containing the node and its neighbors.
        """
        # For MockEngine, return empty subgraph
        return Subgraph(nodes=[], edges=[])

    def mutate(self, graph: Graph, correction: Correction) -> Graph:
        """Apply a correction to the graph.

        Args:
            graph: The graph to mutate.
            correction: The correction to apply.

        Returns:
            New graph with the correction applied.
        """
        if correction.action == "delete":
            # Remove the node and any edges referencing it
            new_nodes = [n for n in graph.nodes if n.id != correction.node_id]
            new_edges = [
                e
                for e in graph.edges
                if e.source_id != correction.node_id and e.target_id != correction.node_id
            ]
            return Graph(nodes=new_nodes, edges=new_edges)

        elif correction.action == "modify" and correction.new_value:
            # Modify the node's label
            new_nodes = []
            for node in graph.nodes:
                if node.id == correction.node_id:
                    # Create new node with updated label
                    new_nodes.append(
                        Node(
                            id=node.id,
                            label=correction.new_value,
                            type=node.type,
                            source=node.source,
                            metadata=node.metadata,
                        )
                    )
                else:
                    new_nodes.append(node)
            return Graph(nodes=new_nodes, edges=list(graph.edges))

        # Unknown action - return unchanged
        return graph

    def persist(self, graph: Graph) -> None:
        """Persist the graph (mock implementation stores in memory).

        Args:
            graph: The graph to persist.
        """
        self._stored_graph = graph


@pytest.fixture
def maya_typical_week_text() -> str:
    """Load maya_typical_week.txt fixture text."""
    fixture_path = FIXTURES_DIR / "maya_typical_week.txt"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def maya_boring_week_text() -> str:
    """Load maya_boring_week.txt fixture text."""
    fixture_path = FIXTURES_DIR / "maya_boring_week.txt"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def maya_edge_cases_text() -> str:
    """Load maya_edge_cases.txt fixture text."""
    fixture_path = FIXTURES_DIR / "maya_edge_cases.txt"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def mock_engine() -> MockEngine:
    """Provide a MockEngine instance for testing."""
    return MockEngine()
