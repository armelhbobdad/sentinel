"""Graph operations for Sentinel.

Pure graph manipulation functions that operate on Graph objects.
This module must NOT import from cli/ or viz/ - it's pure graph logic.
"""

from collections import deque

from sentinel.core.types import Graph, Node


def extract_neighborhood(
    graph: Graph,
    focal_node: Node,
    depth: int = 2,
) -> Graph:
    """Extract a subgraph centered on a focal node.

    Performs BFS traversal to find all nodes within `depth` hops
    of the focal node, then extracts all edges between those nodes.

    Args:
        graph: The full graph to extract from.
        focal_node: The center node for the neighborhood.
        depth: Maximum number of hops from focal node (default: 2).

    Returns:
        A new Graph containing only the neighborhood nodes and their edges.

    Raises:
        ValueError: If depth is negative.
    """
    if depth < 0:
        raise ValueError("Depth must be non-negative")

    if depth == 0:
        # Just the focal node, no connections
        return Graph(nodes=(focal_node,), edges=())

    # Build adjacency map for fast traversal (both directions)
    adjacency: dict[str, set[str]] = {}
    for node in graph.nodes:
        adjacency[node.id] = set()

    for edge in graph.edges:
        # Undirected traversal for neighborhood discovery
        if edge.source_id in adjacency:
            adjacency[edge.source_id].add(edge.target_id)
        if edge.target_id in adjacency:
            adjacency[edge.target_id].add(edge.source_id)

    # BFS to find nodes within depth
    visited: set[str] = {focal_node.id}
    queue: deque[tuple[str, int]] = deque([(focal_node.id, 0)])

    while queue:
        node_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue

        for neighbor_id in adjacency.get(node_id, set()):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append((neighbor_id, current_depth + 1))

    # Extract nodes in neighborhood
    node_map = {n.id: n for n in graph.nodes}
    neighborhood_nodes = tuple(node_map[nid] for nid in visited if nid in node_map)

    # Extract edges between neighborhood nodes
    neighborhood_edges = tuple(
        e for e in graph.edges if e.source_id in visited and e.target_id in visited
    )

    return Graph(nodes=neighborhood_nodes, edges=neighborhood_edges)
