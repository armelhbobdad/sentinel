"""Collision detection rules and graph traversal.

This module implements the collision detection algorithm using multi-hop
graph traversal to find energy collision patterns.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from sentinel.core.constants import (
    AI_INFERRED_PENALTY,
    CROSS_DOMAIN_BOOST,
    DEFAULT_TIMEOUT,
    HEALTH_KEYWORDS,
    MAX_DEPTH,
    METADATA_PROFESSIONAL_HINTS,
    METADATA_SOCIAL_HINTS,
    NODE_TYPE_ACTIVITY,
    NODE_TYPE_ENERGY_STATE,
    NODE_TYPE_PERSON,
    NODE_TYPE_TIME_SLOT,
    PROFESSIONAL_KEYWORDS,
    REL_CONFLICTS_WITH,
    REL_DRAINS,
    REL_REQUIRES,
    SOCIAL_KEYWORDS,
)
from sentinel.core.types import Domain, Edge, Graph, Node, ScoredCollision

logger = logging.getLogger(__name__)


def classify_domain(node: Node) -> Domain:
    """Classify a node into a life domain.

    Classification priority:
    1. Explicit domain in metadata (highest priority)
    2. Metadata hints (relationship, context)
    3. Label keyword matching
    4. PERSONAL fallback

    Args:
        node: The node to classify.

    Returns:
        Domain classification for the node.
    """
    # Priority 1: Check explicit domain in metadata
    if "domain" in node.metadata:
        domain_str = str(node.metadata["domain"]).upper()
        try:
            return Domain[domain_str]
        except KeyError:
            pass  # Invalid domain string, fall through to other methods

    # EnergyState and TimeSlot nodes don't have domains
    if node.type in (NODE_TYPE_ENERGY_STATE, NODE_TYPE_TIME_SLOT):
        return Domain.PERSONAL

    # Priority 2: Check metadata hints
    metadata_str = " ".join(str(v).lower() for v in node.metadata.values())

    # Family/relationship context indicates SOCIAL
    if any(hint in metadata_str for hint in METADATA_SOCIAL_HINTS):
        return Domain.SOCIAL

    # Work context indicates PROFESSIONAL
    if any(hint in metadata_str for hint in METADATA_PROFESSIONAL_HINTS):
        return Domain.PROFESSIONAL

    # Priority 3: Label keyword matching
    # Check more specific keywords first to avoid false positives
    # (e.g., "workout" should match HEALTH, not PROFESSIONAL due to "work" substring)
    label_lower = node.label.lower()

    # Check SOCIAL keywords
    for keyword in SOCIAL_KEYWORDS:
        if keyword in label_lower:
            return Domain.SOCIAL

    # Check HEALTH keywords BEFORE PROFESSIONAL (more specific)
    for keyword in HEALTH_KEYWORDS:
        if keyword in label_lower:
            return Domain.HEALTH

    # Check PROFESSIONAL keywords
    for keyword in PROFESSIONAL_KEYWORDS:
        if keyword in label_lower:
            return Domain.PROFESSIONAL

    # Priority 4: Default fallback
    return Domain.PERSONAL


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
        return (
            REL_DRAINS in relations
            and REL_CONFLICTS_WITH in relations
            and REL_REQUIRES in relations
        )


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
    drains_edges = [e for e in graph.edges if e.relationship == REL_DRAINS]

    for start_edge in drains_edges:
        # BFS from the drained energy state
        visited = {start_edge.source_id, start_edge.target_id}
        bfs_queue: deque[tuple[str, list[Edge]]] = deque([(start_edge.target_id, [start_edge])])

        while bfs_queue:
            current, path = bfs_queue.popleft()

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
                    bfs_queue.append((next_node, path + [edge]))

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
    drains_edges = [e for e in graph.edges if e.relationship == REL_DRAINS]

    for start_edge in drains_edges:
        visited = {start_edge.source_id, start_edge.target_id}
        bfs_queue: deque[tuple[str, list[Edge]]] = deque([(start_edge.target_id, [start_edge])])
        relationships_analyzed += 1

        if progress_callback:
            progress_callback(relationships_analyzed)

        try:
            while bfs_queue:
                # Check timeout for each hop
                async def process_hop() -> bool:
                    nonlocal relationships_analyzed, timed_out
                    if not bfs_queue:
                        return False

                    current, path = bfs_queue.popleft()

                    if len(path) >= max_depth:
                        collision_path = CollisionPath(edges=tuple(path))
                        if collision_path.matches_collision_pattern():
                            paths_builder.append(collision_path)
                        return True

                    for edge in adjacency.get(current, []):
                        next_node = edge.target_id if edge.source_id == current else edge.source_id
                        if next_node not in visited:
                            visited.add(next_node)
                            bfs_queue.append((next_node, path + [edge]))
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


def is_cross_domain_collision(source_domain: Domain, target_domain: Domain) -> bool:
    """Check if collision crosses domain boundaries.

    Cross-domain collisions (e.g., social activity impacting professional
    requirement) are more impactful than same-domain conflicts.

    Args:
        source_domain: Domain of the energy-draining activity.
        target_domain: Domain of the activity requiring energy.

    Returns:
        True if collision crosses domains (more impactful).
    """
    # Same domain is less impactful (expected conflicts)
    if source_domain == target_domain:
        return False

    # Cross-domain collision pairs to flag
    cross_domain_pairs = {
        (Domain.SOCIAL, Domain.PROFESSIONAL),  # Family → Work
        (Domain.PERSONAL, Domain.PROFESSIONAL),  # Personal → Work
        (Domain.SOCIAL, Domain.HEALTH),  # Social → Health
        (Domain.PERSONAL, Domain.HEALTH),  # Personal → Health
        (Domain.HEALTH, Domain.PROFESSIONAL),  # Health → Work
    }

    return (source_domain, target_domain) in cross_domain_pairs


def score_collision_with_domains(path: CollisionPath, graph: Graph) -> ScoredCollision:
    """Enhanced scoring that includes domain classification.

    Builds on score_collision() from Story 2.1 by:
    - Classifying source and target domains
    - Boosting confidence for cross-domain collisions
    - Adding domain labels to path for display

    The collision pattern is: Source -[DRAINS]-> ... -[REQUIRES]<- Target
    - Source: the entity that DRAINS energy (source of DRAINS edge)
    - Target: the activity that REQUIRES energy (source of REQUIRES edge)

    Args:
        path: The collision path to score.
        graph: The graph containing node information.

    Returns:
        ScoredCollision with domain-enhanced confidence and path labels.
    """
    # Get base score from existing function
    base_collision = score_collision(path, graph)

    # Build node lookup
    nodes = {n.id: n for n in graph.nodes}

    # Find the source (DRAINS source) and target (REQUIRES source) nodes
    # The start_node is the source of DRAINS edge
    source_node = nodes.get(path.start_node)

    # Find the REQUIRES edge to get the activity that requires energy
    requires_edge = next((e for e in path.edges if e.relationship == REL_REQUIRES), None)
    target_node = nodes.get(requires_edge.source_id) if requires_edge else None

    if not source_node or not target_node:
        # Cannot classify domains, return base collision
        return base_collision

    # Classify domains
    source_domain = classify_domain(source_node)
    target_domain = classify_domain(target_node)

    # Enhance path labels with domain info
    # Find the source and target labels in the path and enhance them
    enhanced_path = list(base_collision.path)

    # Enhance first element (source node label)
    if enhanced_path:
        enhanced_path[0] = f"[{source_domain.name}] {enhanced_path[0]}"

    # Find and enhance the target activity label in the path
    # The REQUIRES edge source is the activity that needs energy
    if target_node and enhanced_path:
        for i, label in enumerate(enhanced_path):
            if label == target_node.label:
                enhanced_path[i] = f"[{target_domain.name}] {label}"
                break

    # Boost confidence for cross-domain collisions
    confidence = base_collision.confidence
    if is_cross_domain_collision(source_domain, target_domain):
        confidence = min(1.0, confidence * CROSS_DOMAIN_BOOST)

    return ScoredCollision(
        path=tuple(enhanced_path),
        confidence=confidence,
        source_breakdown=base_collision.source_breakdown,
    )


def is_valid_collision(path: CollisionPath, graph: Graph) -> bool:
    """Validate collision path to prevent false positives.

    Checks:
    1. Minimum 3 edges (DRAINS → CONFLICTS_WITH → REQUIRES)
    2. Matches collision pattern
    3. Start and end nodes are different (no self-loops)
    4. Start is Person or Activity, end of REQUIRES is Activity

    Args:
        path: The collision path to validate.
        graph: The graph for context.

    Returns:
        True if collision is valid, False if it's a false positive.
    """
    # Rule 1: Must have minimum 3 edges
    if len(path.edges) < 3:
        return False

    # Rule 2: Must match collision pattern
    if not path.matches_collision_pattern():
        return False

    # Rule 3: Start and end must be different nodes (no self-loops)
    if path.start_node == path.end_node:
        return False

    # Build node lookup for type checking
    nodes = {n.id: n for n in graph.nodes}

    # Rule 4: Start node must be Person or Activity
    start_node = nodes.get(path.start_node)
    if start_node and start_node.type not in (NODE_TYPE_PERSON, NODE_TYPE_ACTIVITY):
        return False

    # Rule 5: REQUIRES edge source must be an Activity
    requires_edge = next((e for e in path.edges if e.relationship == REL_REQUIRES), None)
    if requires_edge:
        requires_source = nodes.get(requires_edge.source_id)
        if requires_source and requires_source.type != NODE_TYPE_ACTIVITY:
            return False

    return True


def deduplicate_collisions(collisions: list[ScoredCollision]) -> list[ScoredCollision]:
    """Remove duplicate collision paths, keeping highest confidence.

    Duplicates are identified by their path tuple.

    Args:
        collisions: List of scored collisions to deduplicate.

    Returns:
        List with duplicates removed, keeping highest confidence version.
    """
    # Use dict to track best collision for each path
    best_by_path: dict[tuple[str, ...], ScoredCollision] = {}

    for collision in collisions:
        path_key = collision.path
        existing = best_by_path.get(path_key)

        if existing is None or collision.confidence > existing.confidence:
            best_by_path[path_key] = collision

    return list(best_by_path.values())


def detect_cross_domain_collisions(graph: Graph) -> list[ScoredCollision]:
    """Detect collision patterns with domain-aware scoring.

    This is the main entry point for Story 2.2 collision detection.
    It uses the Story 2.1 traversal infrastructure and enhances it
    with domain classification and false positive prevention.

    Args:
        graph: The graph to search for collision patterns.

    Returns:
        List of ScoredCollision objects with domain information.
    """
    # Use Story 2.1's path finding
    paths = find_collision_paths(graph)

    if not paths:
        return []

    # Filter out invalid paths (false positive prevention)
    valid_paths = [p for p in paths if is_valid_collision(p, graph)]

    if not valid_paths:
        return []

    # Score each path with domain enhancement
    collisions = [score_collision_with_domains(path, graph) for path in valid_paths]

    # Deduplicate paths
    collisions = deduplicate_collisions(collisions)

    # Sort by confidence (highest first), prioritizing cross-domain
    collisions.sort(key=lambda c: c.confidence, reverse=True)

    return collisions
