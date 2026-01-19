"""ASCII graph visualization using phart.

This module converts Sentinel Graph objects to NetworkX DiGraphs
and renders them as ASCII art using the phart library.
"""

import logging

import networkx as nx
from phart import ASCIIRenderer, NodeStyle

from sentinel.core.types import Graph, Node

logger = logging.getLogger(__name__)

# Maximum nodes for full render before showing warning
MAX_NODES_FOR_FULL_RENDER = 50


def _format_node_label(node: Node) -> str:
    """Format node label with source-appropriate brackets.

    Args:
        node: The node to format.

    Returns:
        Label with brackets: [label] for user-stated, (label) for ai-inferred.
    """
    if node.source == "user-stated":
        return f"[{node.label}]"
    return f"({node.label})"


def graph_to_networkx(graph: Graph) -> nx.DiGraph:
    """Convert Sentinel Graph to NetworkX DiGraph for phart.

    Uses formatted labels as node IDs so phart displays styled labels.

    Args:
        graph: Sentinel Graph with nodes and edges.

    Returns:
        NetworkX DiGraph with nodes and edges suitable for phart rendering.
    """
    graph_nx = nx.DiGraph()

    # Map original node ID to formatted label for edge lookups
    id_to_label: dict[str, str] = {}

    for node in graph.nodes:
        formatted_label = _format_node_label(node)
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


def render_ascii(graph: Graph) -> str:
    """Render Graph as ASCII art using phart.

    Args:
        graph: Sentinel Graph to render.

    Returns:
        ASCII art representation of the graph, or friendly message if empty.
        For large graphs (>50 nodes), includes a warning and summary.
    """
    if not graph.nodes:
        return "No entities found in your schedule. Try adding more details."

    try:
        parts: list[str] = []

        # Warn about large graphs (plain text, no Rich markup - output uses markup=False)
        if len(graph.nodes) > MAX_NODES_FOR_FULL_RENDER:
            parts.append(
                f"⚠ Large graph detected ({len(graph.nodes)} nodes). Showing summary view."
            )
            parts.append("")

        nx_graph = graph_to_networkx(graph)

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
