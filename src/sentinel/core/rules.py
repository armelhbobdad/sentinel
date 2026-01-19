"""Collision detection rules and graph traversal.

This module implements the collision detection algorithm using multi-hop
graph traversal to find energy collision patterns.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from sentinel.core.constants import AI_INFERRED_PENALTY, DEFAULT_TIMEOUT, MAX_DEPTH
from sentinel.core.types import Edge, Graph, ScoredCollision

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollisionPath:
    """A path of edges representing a potential collision.

    Attributes:
        edges: Tuple of edges forming the path.
    """

    edges: tuple[Edge, ...]

    @property
    def start_node(self) -> str:
        """Return the source node ID of the first edge."""
        return self.edges[0].source_id

    @property
    def end_node(self) -> str:
        """Return the target node ID of the last edge."""
        return self.edges[-1].target_id

    def matches_collision_pattern(self) -> bool:
        """Check if path matches DRAINS → CONFLICTS_WITH → REQUIRES pattern.

        Returns:
            True if path contains all three required relationship types.
        """
        if len(self.edges) < 3:
            return False

        relations = {e.relationship for e in self.edges}
        # Pattern: DRAINS → CONFLICTS_WITH → REQUIRES
        # Or reverse: REQUIRES ← CONFLICTS_WITH ← DRAINS
        return "DRAINS" in relations and "CONFLICTS_WITH" in relations and "REQUIRES" in relations


def get_node_edges(graph: Graph, node_id: str) -> tuple[Edge, ...]:
    """Get all edges connected to a node (incoming and outgoing).

    Args:
        graph: The graph to search.
        node_id: ID of the node to find edges for.

    Returns:
        Tuple of edges where node_id is source or target.
        Returns empty tuple if node has no connections.
    """
    edges = [edge for edge in graph.edges if edge.source_id == node_id or edge.target_id == node_id]
    return tuple(edges)


def _build_adjacency_list(graph: Graph) -> dict[str, list[Edge]]:
    """Build adjacency list for efficient neighbor lookup.

    Args:
        graph: Graph to build adjacency list from.

    Returns:
        Dict mapping node IDs to list of connected edges.
    """
    adj: dict[str, list[Edge]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.source_id, []).append(edge)
        adj.setdefault(edge.target_id, []).append(edge)  # Bidirectional for traversal
    return adj


def find_collision_paths(graph: Graph, max_depth: int = 3) -> list[CollisionPath]:
    """Find all paths that could indicate energy collisions.

    Strategy:
    1. Find all nodes connected by DRAINS edges (energy drainers)
    2. BFS from each to find CONFLICTS_WITH → REQUIRES paths
    3. Return paths of length >= max_depth matching collision pattern

    Args:
        graph: The graph to search for collision patterns.
        max_depth: Minimum path length to consider (default 3).

    Returns:
        List of CollisionPath objects matching the collision pattern.
    """
    paths: list[CollisionPath] = []

    if not graph.edges:
        return paths

    # Build adjacency list for efficient traversal
    adjacency = _build_adjacency_list(graph)

    # Find DRAINS edges as starting points
    drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]

    for start_edge in drains_edges:
        # BFS from the drained energy state
        visited = {start_edge.source_id, start_edge.target_id}
        queue: list[tuple[str, list[Edge]]] = [(start_edge.target_id, [start_edge])]

        while queue:
            current, path = queue.pop(0)

            if len(path) >= max_depth:
                collision_path = CollisionPath(edges=tuple(path))
                if collision_path.matches_collision_pattern():
                    paths.append(collision_path)
                continue

            for edge in adjacency.get(current, []):
                # Determine next node (the other end of the edge)
                next_node = edge.target_id if edge.source_id == current else edge.source_id
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, path + [edge]))

    return paths


@dataclass(frozen=True)
class TraversalResult:
    """Result of collision path traversal.

    Attributes:
        paths: Tuple of collision paths found (immutable).
        timed_out: True if traversal timed out before completion.
        relationships_analyzed: Count of relationships analyzed.
    """

    paths: tuple[CollisionPath, ...] = ()
    timed_out: bool = False
    relationships_analyzed: int = 0


async def find_collision_paths_async(
    graph: Graph,
    max_depth: int = MAX_DEPTH,
    hop_timeout: float = DEFAULT_TIMEOUT,
    progress_callback: Callable[[int], None] | None = None,
) -> TraversalResult:
    """Find collision paths asynchronously with timeout support.

    Args:
        graph: The graph to search for collision patterns.
        max_depth: Minimum path length to consider (default 3).
        hop_timeout: Timeout in seconds for each traversal hop (default 5).
        progress_callback: Optional callback called with relationship count.

    Returns:
        TraversalResult containing found paths and timeout status.
    """
    # Use list internally for efficient appending, convert to tuple at end
    paths_builder: list[CollisionPath] = []
    relationships_analyzed = 0
    timed_out = False

    if not graph.edges:
        return TraversalResult(
            paths=(),
            timed_out=False,
            relationships_analyzed=0,
        )

    # Build adjacency list
    adjacency = _build_adjacency_list(graph)

    # Find DRAINS edges as starting points
    drains_edges = [e for e in graph.edges if e.relationship == "DRAINS"]

    for start_edge in drains_edges:
        visited = {start_edge.source_id, start_edge.target_id}
        queue: list[tuple[str, list[Edge]]] = [(start_edge.target_id, [start_edge])]
        relationships_analyzed += 1

        if progress_callback:
            progress_callback(relationships_analyzed)

        try:
            while queue:
                # Check timeout for each hop
                async def process_hop() -> bool:
                    nonlocal relationships_analyzed, timed_out
                    if not queue:
                        return False

                    current, path = queue.pop(0)

                    if len(path) >= max_depth:
                        collision_path = CollisionPath(edges=tuple(path))
                        if collision_path.matches_collision_pattern():
                            paths_builder.append(collision_path)
                        return True

                    for edge in adjacency.get(current, []):
                        next_node = edge.target_id if edge.source_id == current else edge.source_id
                        if next_node not in visited:
                            visited.add(next_node)
                            queue.append((next_node, path + [edge]))
                            relationships_analyzed += 1

                            if progress_callback:
                                progress_callback(relationships_analyzed)

                    return True

                # Apply timeout to each hop
                await asyncio.wait_for(process_hop(), timeout=hop_timeout)

        except TimeoutError:
            logger.warning("Traversal timed out after %d relationships", relationships_analyzed)
            timed_out = True
            break

    return TraversalResult(
        paths=tuple(paths_builder),
        timed_out=timed_out,
        relationships_analyzed=relationships_analyzed,
    )


def score_collision(path: CollisionPath, graph: Graph) -> ScoredCollision:
    """Calculate confidence score for a collision path.

    Score based on:
    - Edge confidence values
    - Source labels (user-stated vs ai-inferred)

    Args:
        path: The collision path to score.
        graph: The graph containing node information.

    Returns:
        ScoredCollision with confidence and source breakdown.
    """
    # Average edge confidence
    avg_confidence = sum(e.confidence for e in path.edges) / len(path.edges)

    # Collect all node IDs in the path
    node_ids = set()
    for edge in path.edges:
        node_ids.add(edge.source_id)
        node_ids.add(edge.target_id)

    # Build node lookup
    nodes = {n.id: n for n in graph.nodes}

    # Count AI-inferred vs user-stated
    ai_inferred_count = 0
    user_stated_count = 0

    for nid in node_ids:
        node = nodes.get(nid)
        if node:
            if node.source == "ai-inferred":
                ai_inferred_count += 1
            else:
                user_stated_count += 1

    # Reduce confidence for AI-inferred components
    # Each AI-inferred node reduces confidence by penalty factor
    confidence = avg_confidence * (AI_INFERRED_PENALTY**ai_inferred_count)

    # Build path labels for display
    path_labels: list[str] = []
    for edge in path.edges:
        source_node = nodes.get(edge.source_id)
        if source_node and source_node.label not in path_labels:
            path_labels.append(source_node.label)
        path_labels.append(edge.relationship)
    # Add final target
    if path.edges:
        final_target = nodes.get(path.edges[-1].target_id)
        if final_target:
            path_labels.append(final_target.label)

    # Use MappingProxyType for true immutability
    source_breakdown = MappingProxyType(
        {
            "ai_inferred": ai_inferred_count,
            "user_stated": user_stated_count,
        }
    )

    return ScoredCollision(
        path=tuple(path_labels),  # Convert to immutable tuple
        confidence=confidence,
        source_breakdown=source_breakdown,
    )
