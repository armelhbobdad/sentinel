"""Semantic node consolidation for reliable path finding (BUG-003).

This module pre-processes graphs to merge semantically equivalent nodes,
enabling BFS path-finding to traverse collision patterns even when the
LLM generates lexically different but semantically equivalent node IDs.

Strategy:
1. Compute similarity between node labels using RapidFuzz
2. Group similar nodes with energy keyword boost
3. Select canonical representative (shortest label)
4. Rewrite edge references to use canonical IDs
"""

import logging

from rapidfuzz import fuzz

from sentinel.core.constants import (
    ENERGY_KEYWORD_BOOST,
    ENERGY_STATE_KEYWORDS,
    NODE_SIMILARITY_THRESHOLD,
)
from sentinel.core.types import Edge, Graph, Node

logger = logging.getLogger(__name__)


def compute_similarity(label1: str, label2: str) -> int:
    """Compute similarity between two labels with energy keyword boost.

    Uses RapidFuzz WRatio for robust partial matching, then applies
    a boost if both labels contain energy-related keywords AND have
    base lexical similarity >= 40.

    The base similarity threshold ensures we only boost labels that are
    already somewhat similar lexically, preventing incorrect merges of
    semantically opposite energy states (e.g., "drained" vs "focused").

    Args:
        label1: First label to compare.
        label2: Second label to compare.

    Returns:
        Similarity score from 0 to 100 (capped).
    """
    # Normalize to lowercase for comparison
    label1_lower = label1.lower()
    label2_lower = label2.lower()

    # Base similarity using WRatio (handles partial matches, reordering)
    # Cast to int since RapidFuzz returns float but we use int thresholds
    base_score = int(fuzz.WRatio(label1_lower, label2_lower))

    # Check if both labels contain energy keywords
    label1_has_energy = any(kw in label1_lower for kw in ENERGY_STATE_KEYWORDS)
    label2_has_energy = any(kw in label2_lower for kw in ENERGY_STATE_KEYWORDS)

    # Only apply boost if:
    # 1. Both labels have energy keywords, AND
    # 2. Base similarity is >= 40 (ensures some lexical overlap first)
    # This prevents merging semantically opposite energy states like "drained" vs "focused"
    if label1_has_energy and label2_has_energy and base_score >= 40:
        # Boost similarity for energy-related labels
        return min(100, base_score + ENERGY_KEYWORD_BOOST)

    return base_score


def _has_energy_keyword(label: str) -> bool:
    """Check if a label contains any energy-related keyword."""
    label_lower = label.lower()
    return any(kw in label_lower for kw in ENERGY_STATE_KEYWORDS)


def group_similar_nodes(
    nodes: list[Node], threshold: int = NODE_SIMILARITY_THRESHOLD
) -> list[list[Node]]:
    """Group nodes by label similarity using RapidFuzz.

    IMPORTANT: Only energy-related nodes (those with energy keywords) are
    candidates for grouping. Non-energy nodes (activities, persons, timeslots)
    remain in singleton groups to prevent incorrect merges like
    "strategy presentation with exec team" being merged with "executive team".

    Uses a greedy grouping algorithm: for each ungrouped energy node, find all
    similar ungrouped energy nodes and form a group.

    Args:
        nodes: List of nodes to group.
        threshold: Minimum similarity score (0-100) to group nodes.

    Returns:
        List of node groups, where each group contains similar nodes.
    """
    if not nodes:
        return []

    groups: list[list[Node]] = []
    used: set[str] = set()

    for node in nodes:
        if node.id in used:
            continue

        # Start a new group with this node
        group = [node]
        used.add(node.id)

        # Only try to group energy-related nodes
        # Non-energy nodes stay in singleton groups to prevent false merges
        if _has_energy_keyword(node.label):
            # Find all similar ungrouped energy nodes
            for other in nodes:
                if other.id not in used and _has_energy_keyword(other.label):
                    score = compute_similarity(node.label, other.label)
                    if score >= threshold:
                        group.append(other)
                        used.add(other.id)

        groups.append(group)

    return groups


def select_canonical_node(group: list[Node]) -> Node:
    """Select the canonical representative from a group of similar nodes.

    Selection criteria: prefer shorter, more specific labels.
    Ties broken alphabetically for determinism.

    Args:
        group: Non-empty list of similar nodes.

    Returns:
        The canonical node (shortest label, then alphabetically first).

    Raises:
        ValueError: If group is empty.
    """
    if not group:
        raise ValueError("Cannot select canonical node from empty group")

    return min(group, key=lambda n: (len(n.label), n.label))


def consolidate_semantic_nodes(graph: Graph) -> Graph:
    """Consolidate semantically equivalent nodes for reliable path finding.

    Pre-processes the graph to merge nodes with similar labels, enabling
    BFS path-finding to traverse collision patterns even when the LLM
    generates different but equivalent node IDs.

    Strategy:
    1. Group nodes by semantic similarity (RapidFuzz + energy boost)
    2. Select canonical representative per group (shortest label)
    3. Build ID mapping (original → canonical)
    4. Rewrite edge source/target IDs
    5. Deduplicate merged nodes

    Args:
        graph: Original graph with potentially duplicate semantic nodes.

    Returns:
        New Graph with consolidated nodes (original graph unchanged).
    """
    if not graph.nodes:
        return graph

    # Group similar nodes
    groups = group_similar_nodes(list(graph.nodes))

    # Build ID mapping: original_id → canonical_id
    id_mapping: dict[str, str] = {}
    canonical_nodes: list[Node] = []

    for group in groups:
        canonical = select_canonical_node(group)
        canonical_nodes.append(canonical)
        for node in group:
            id_mapping[node.id] = canonical.id

    # Log consolidation stats
    merged_count = len(graph.nodes) - len(canonical_nodes)
    if merged_count > 0:
        logger.debug(
            "Consolidated %d nodes into %d (merged %d)",
            len(graph.nodes),
            len(canonical_nodes),
            merged_count,
        )

    # Rewrite edge references
    new_edges: list[Edge] = []
    for edge in graph.edges:
        new_source = id_mapping.get(edge.source_id, edge.source_id)
        new_target = id_mapping.get(edge.target_id, edge.target_id)

        # Create new edge with updated IDs (if changed)
        if new_source != edge.source_id or new_target != edge.target_id:
            new_edge = Edge(
                source_id=new_source,
                target_id=new_target,
                relationship=edge.relationship,
                confidence=edge.confidence,
                metadata=edge.metadata,
            )
            new_edges.append(new_edge)
        else:
            new_edges.append(edge)

    return Graph(nodes=tuple(canonical_nodes), edges=tuple(new_edges))
