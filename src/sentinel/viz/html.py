"""HTML graph visualization module.

Generates self-contained HTML files with SVG-based graph visualization.
Uses circle layout for node positioning and inline CSS for styling.
"""

import logging
import math
from datetime import UTC, datetime

from sentinel.core.types import Edge, Graph, Node

logger = logging.getLogger(__name__)

# SVG dimensions
SVG_WIDTH = 800
SVG_HEIGHT = 600
SVG_MARGIN = 80

# Node styling colors
COLOR_USER_STATED = "#4CAF50"  # Green
COLOR_AI_INFERRED = "#9E9E9E"  # Gray
COLOR_EDGE = "#333333"  # Dark gray
COLOR_COLLISION = "#F44336"  # Red
COLOR_EDGE_LABEL = "#666666"  # Medium gray

# Node dimensions
NODE_RADIUS = 8
LABEL_OFFSET = 12


def _calculate_node_positions(
    nodes: tuple[Node, ...],
    width: int = SVG_WIDTH,
    height: int = SVG_HEIGHT,
) -> dict[str, tuple[float, float]]:
    """Calculate node positions using circle layout.

    Args:
        nodes: Tuple of nodes to position.
        width: SVG width in pixels.
        height: SVG height in pixels.

    Returns:
        Dictionary mapping node IDs to (x, y) coordinates.
    """
    positions: dict[str, tuple[float, float]] = {}
    n = len(nodes)

    if n == 0:
        return positions

    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - SVG_MARGIN

    # Single node: center it
    if n == 1:
        positions[nodes[0].id] = (cx, cy)
        return positions

    # Multiple nodes: arrange in circle
    for i, node in enumerate(nodes):
        angle = (2 * math.pi * i) / n - math.pi / 2  # Start from top
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        positions[node.id] = (x, y)

    return positions


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Text to escape.

    Returns:
        HTML-safe text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _generate_node_svg(
    node: Node,
    x: float,
    y: float,
    is_collision: bool = False,
) -> str:
    """Generate SVG elements for a single node.

    Args:
        node: The node to render.
        x: X coordinate for node center.
        y: Y coordinate for node center.
        is_collision: Whether node is part of collision path.

    Returns:
        SVG string containing circle and text elements.
    """
    # Determine color based on source
    if node.source == "user-stated":
        fill_color = COLOR_USER_STATED
        css_class = "node user-stated"
    else:
        fill_color = COLOR_AI_INFERRED
        css_class = "node ai-inferred"

    # Add collision styling if needed
    if is_collision:
        css_class += " collision"

    # Escape label for HTML
    safe_label = _escape_html(node.label)

    text_y = y + LABEL_OFFSET + NODE_RADIUS
    return f"""    <g class="{css_class}">
      <circle cx="{x:.1f}" cy="{y:.1f}" r="{NODE_RADIUS}" fill="{fill_color}" />
      <text x="{x:.1f}" y="{text_y:.1f}" text-anchor="middle" class="node-label">{safe_label}</text>
    </g>"""


def _generate_edge_svg(
    edge: Edge,
    positions: dict[str, tuple[float, float]],
    is_collision: bool = False,
) -> str:
    """Generate SVG elements for a single edge.

    Args:
        edge: The edge to render.
        positions: Dictionary mapping node IDs to coordinates.
        is_collision: Whether edge is part of collision path.

    Returns:
        SVG string containing line and optional text elements.
    """
    if edge.source_id not in positions or edge.target_id not in positions:
        return ""

    x1, y1 = positions[edge.source_id]
    x2, y2 = positions[edge.target_id]

    # Calculate midpoint for label
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2

    # Determine styling
    css_class = "edge collision-highlight" if is_collision else "edge"
    stroke_color = COLOR_COLLISION if is_collision else COLOR_EDGE
    stroke_width = 3 if is_collision else 1.5

    # Escape relationship label
    safe_label = _escape_html(edge.relationship)

    label_y = my - 5
    line_elem = (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width}" marker-end="url(#arrowhead)" />'
    )
    text_elem = (
        f'<text x="{mx:.1f}" y="{label_y:.1f}" '
        f'text-anchor="middle" class="edge-label">{safe_label}</text>'
    )
    return f"""    <g class="{css_class}">
      {line_elem}
      {text_elem}
    </g>"""


def _generate_css() -> str:
    """Generate inline CSS styles.

    Returns:
        CSS stylesheet content.
    """
    return f"""    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        margin: 0;
        padding: 20px;
        background: #fafafa;
        color: #333;
      }}
      h1 {{
        margin: 0 0 20px 0;
        font-size: 24px;
        font-weight: 600;
      }}
      .graph-container {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 20px;
        margin-bottom: 20px;
      }}
      svg {{
        display: block;
        margin: 0 auto;
      }}
      .node circle {{
        stroke: #fff;
        stroke-width: 2;
      }}
      .node.user-stated circle {{
        fill: {COLOR_USER_STATED};
      }}
      .node.ai-inferred circle {{
        fill: {COLOR_AI_INFERRED};
      }}
      .node.collision circle {{
        stroke: {COLOR_COLLISION};
        stroke-width: 3;
      }}
      .node-label {{
        font-size: 12px;
        fill: #333;
      }}
      .edge line {{
        stroke: {COLOR_EDGE};
        stroke-width: 1.5;
      }}
      .edge.collision-highlight line {{
        stroke: {COLOR_COLLISION};
        stroke-width: 3;
      }}
      .edge-label {{
        font-size: 10px;
        fill: {COLOR_EDGE_LABEL};
      }}
      .legend {{
        margin-top: 20px;
        padding: 15px;
        background: #f5f5f5;
        border-radius: 4px;
        font-size: 14px;
      }}
      .legend-item {{
        display: inline-flex;
        align-items: center;
        margin-right: 20px;
      }}
      .legend-dot {{
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 6px;
      }}
      .legend-dot.user-stated {{
        background: {COLOR_USER_STATED};
      }}
      .legend-dot.ai-inferred {{
        background: {COLOR_AI_INFERRED};
      }}
      .legend-dot.collision {{
        background: {COLOR_COLLISION};
      }}
      footer {{
        margin-top: 20px;
        font-size: 12px;
        color: #999;
      }}
      .collisions {{
        margin-bottom: 20px;
      }}
      .collision-card {{
        background: #fff3f3;
        border-left: 4px solid {COLOR_COLLISION};
        padding: 12px 16px;
        margin-bottom: 10px;
        border-radius: 0 4px 4px 0;
      }}
      .collision-card .path {{
        font-family: monospace;
        margin: 0 0 8px 0;
      }}
      .collision-card .confidence {{
        color: #666;
        margin: 0;
        font-size: 13px;
      }}
      .empty-state {{
        text-align: center;
        padding: 40px;
        color: #666;
      }}
    </style>"""


def _generate_svg_defs() -> str:
    """Generate SVG definitions (markers, etc.).

    Returns:
        SVG defs element content.
    """
    return """  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#333" />
    </marker>
  </defs>"""


def _generate_collision_cards(collision_paths: list[tuple[str, ...]]) -> str:
    """Generate HTML for collision warning cards.

    Args:
        collision_paths: List of collision path tuples.

    Returns:
        HTML string for collision warnings section.
    """
    if not collision_paths:
        return ""

    cards: list[str] = []
    for i, path in enumerate(collision_paths, 1):
        # Format path with arrows
        formatted_parts = []
        for j, element in enumerate(path):
            safe_element = _escape_html(element)
            if j % 2 == 0:  # Entity
                formatted_parts.append(f"<strong>{safe_element}</strong>")
            else:  # Relationship
                formatted_parts.append(f"<em>{safe_element}</em>")
        path_str = " → ".join(formatted_parts)

        cards.append(f"""    <div class="collision-card">
      <p class="path">#{i}: {path_str}</p>
    </div>""")

    return f"""  <section class="collisions">
    <h2>⚠️ Collision Warnings</h2>
{"".join(cards)}
  </section>"""


def render_html(
    graph: Graph,
    collision_paths: list[tuple[str, ...]] | None = None,
    title: str | None = None,
) -> str:
    """Generate self-contained HTML with SVG graph visualization.

    Args:
        graph: Sentinel Graph to visualize.
        collision_paths: Optional list of collision path tuples for highlighting.
        title: Optional custom title for the HTML page.

    Returns:
        Complete HTML document as a string.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    page_title = title or f"Sentinel Graph - {timestamp}"

    # Build set of collision node labels and edge pairs for highlighting
    collision_labels: set[str] = set()
    collision_edges: set[tuple[str, str]] = set()
    if collision_paths:
        for path in collision_paths:
            # Extract entities (even indices: 0, 2, 4, ...)
            entities = [path[i] for i in range(0, len(path), 2)]
            # Add all entities to collision labels
            for entity in entities:
                collision_labels.add(entity)
            # Add edges between consecutive entities
            for j in range(len(entities) - 1):
                collision_edges.add((entities[j], entities[j + 1]))

    # Calculate positions
    positions = _calculate_node_positions(graph.nodes)

    # Build node lookup for O(1) access (performance optimization)
    nodes_by_id: dict[str, Node] = {n.id: n for n in graph.nodes}

    # Handle empty graph
    if not graph.nodes:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape_html(page_title)}</title>
{_generate_css()}
</head>
<body>
  <h1>Sentinel Energy Graph</h1>
  <div class="graph-container">
    <div class="empty-state">
      <p>No data available. Import your schedule to visualize your energy graph.</p>
    </div>
  </div>
  <footer>
    <p>Generated by Sentinel at {timestamp}</p>
  </footer>
</body>
</html>"""

    # Generate edges first (so they render behind nodes)
    edge_svgs: list[str] = []
    for edge in graph.edges:
        # Check if edge is part of collision path (O(1) lookup)
        source_node = nodes_by_id.get(edge.source_id)
        target_node = nodes_by_id.get(edge.target_id)
        is_collision = False
        if source_node and target_node:
            is_collision = (source_node.label, target_node.label) in collision_edges

        edge_svg = _generate_edge_svg(edge, positions, is_collision=is_collision)
        if edge_svg:
            edge_svgs.append(edge_svg)

    # Generate nodes
    node_svgs: list[str] = []
    for node in graph.nodes:
        if node.id in positions:
            x, y = positions[node.id]
            is_collision = node.label in collision_labels
            node_svg = _generate_node_svg(node, x, y, is_collision=is_collision)
            node_svgs.append(node_svg)

    # Combine SVG
    viewbox = f"0 0 {SVG_WIDTH} {SVG_HEIGHT}"
    svg_attrs = f'viewBox="{viewbox}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}"'
    svg_content = f"""  <svg {svg_attrs}>
{_generate_svg_defs()}
    <!-- Edges -->
{"".join(edge_svgs)}
    <!-- Nodes -->
{"".join(node_svgs)}
  </svg>"""

    # Generate collision warning cards if paths provided
    collision_cards_html = _generate_collision_cards(collision_paths or [])

    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape_html(page_title)}</title>
{_generate_css()}
</head>
<body>
  <h1>Sentinel Energy Graph</h1>
{collision_cards_html}
  <div class="graph-container">
{svg_content}
  </div>
  <div class="legend">
    <span class="legend-item">
      <span class="legend-dot user-stated"></span>
      User-stated
    </span>
    <span class="legend-item">
      <span class="legend-dot ai-inferred"></span>
      AI-inferred
    </span>
    <span class="legend-item">
      <span class="legend-dot collision"></span>
      Collision path
    </span>
  </div>
  <footer>
    <p>Generated by Sentinel at {timestamp}</p>
    <p>Nodes: {len(graph.nodes)} | Relationships: {len(graph.edges)}</p>
  </footer>
</body>
</html>"""

    return html
