"""ASCII graph visualization using phart.

This module converts Sentinel Graph objects to NetworkX DiGraphs
and renders them as ASCII art using the phart library.
"""

import logging

import networkx as nx
from phart import ASCIIRenderer, NodeStyle

from sentinel.core.types import Graph, Node, strip_domain_prefix

logger = logging.getLogger(__name__)

# Maximum nodes for full render before showing warning
MAX_NODES_FOR_FULL_RENDER = 50


def _format_node_label(node: Node, highlight: bool = False) -> str:
    """Format node label with source-appropriate brackets.

    Args:
        node: The node to format.
        highlight: Whether to add collision highlight marker.

    Returns:
        Label with brackets: [label] for user-stated, (label) for ai-inferred.
        If highlighted, adds ">>" prefix to indicate collision involvement.
    """
    if node.source == "user-stated":
        base = f"[{node.label}]"
    else:
        base = f"({node.label})"

    if highlight:
        return f">> {base}"
    return base


def graph_to_networkx(
    graph: Graph,
    highlight_labels: set[str] | None = None,
) -> nx.DiGraph:
    """Convert Sentinel Graph to NetworkX DiGraph for phart.

    Uses formatted labels as node IDs so phart displays styled labels.

    Args:
        graph: Sentinel Graph with nodes and edges.
        highlight_labels: Optional set of node labels to highlight
            (for collision path visualization).

    Returns:
        NetworkX DiGraph with nodes and edges suitable for phart rendering.
    """
    graph_nx = nx.DiGraph()
    highlight_set = highlight_labels or set()

    # Map original node ID to formatted label for edge lookups
    id_to_label: dict[str, str] = {}

    for node in graph.nodes:
        should_highlight = node.label in highlight_set
        formatted_label = _format_node_label(node, highlight=should_highlight)
        id_to_label[node.id] = formatted_label
        graph_nx.add_node(
            formatted_label,  # Use formatted label as node ID
            original_id=node.id,
            source=node.source,
        )

    for edge in graph.edges:
        source_label = id_to_label.get(edge.source_id, edge.source_id)
        target_label = id_to_label.get(edge.target_id, edge.target_id)
        graph_nx.add_edge(
            source_label,
            target_label,
            label=edge.relationship,
        )

    return graph_nx


def _format_relationships(graph: Graph) -> str:
    """Format edge relationships for display.

    Args:
        graph: Sentinel Graph with edges.

    Returns:
        Formatted string showing all relationships (deduplicated).
    """
    if not graph.edges:
        return ""

    # Map node IDs to formatted labels
    id_to_label: dict[str, str] = {}
    for node in graph.nodes:
        id_to_label[node.id] = _format_node_label(node)

    # Use set to deduplicate edges
    seen_edges: set[tuple[str, str, str]] = set()
    lines = ["Relationships:"]
    for edge in graph.edges:
        source = id_to_label.get(edge.source_id, edge.source_id)
        target = id_to_label.get(edge.target_id, edge.target_id)
        edge_key = (source, edge.relationship, target)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            lines.append(f"  {source} --{edge.relationship}--> {target}")

    return "\n".join(lines)


def render_ascii(
    graph: Graph,
    collision_paths: list[tuple[str, ...]] | None = None,
) -> str:
    """Render Graph as ASCII art using phart.

    Args:
        graph: Sentinel Graph to render.
        collision_paths: Optional list of collision path tuples. Each path
            contains alternating entity labels and relationship names.
            Entities in these paths will be highlighted with ">>" prefix.

    Returns:
        ASCII art representation of the graph, or friendly message if empty.
        For large graphs (>50 nodes), includes a warning and summary.
    """
    if not graph.nodes:
        return "No entities found in your schedule. Try adding more details."

    # Extract entity labels from collision paths (even indices are entities)
    highlight_labels: set[str] = set()
    if collision_paths:
        for path in collision_paths:
            for i, element in enumerate(path):
                if i % 2 == 0:  # Entity at even index
                    # Strip domain prefix if present (e.g., "[SOCIAL] Aunt Susan" -> "Aunt Susan")
                    highlight_labels.add(strip_domain_prefix(element))

    try:
        parts: list[str] = []

        # Warn about large graphs (plain text, no Rich markup - output uses markup=False)
        if len(graph.nodes) > MAX_NODES_FOR_FULL_RENDER:
            parts.append(
                f"⚠ Large graph detected ({len(graph.nodes)} nodes). Showing summary view."
            )
            parts.append("")

        nx_graph = graph_to_networkx(graph, highlight_labels=highlight_labels)

        # Use MINIMAL style since labels already have brackets
        renderer = ASCIIRenderer(nx_graph, node_style=NodeStyle.MINIMAL)
        graph_output = renderer.render()

        parts.append(graph_output.strip())

        # Add relationships section showing edge labels
        relationships = _format_relationships(graph)
        if relationships:
            parts.append("")  # Blank line
            parts.append(relationships)

        return "\n".join(parts)

    except Exception as e:
        logger.warning("Visualization failed: %s", e)
        return "⚠ Could not render graph visualization."
