"""Tests for HTML graph visualization module.

Tests render_html() function which generates self-contained HTML
with SVG-based graph visualization.
"""

import pytest

from sentinel.core.types import Edge, Graph, Node


@pytest.fixture
def mock_graph() -> Graph:
    """Create a sample graph for testing."""
    nodes = (
        Node(id="n1", label="Maya", type="Person", source="user-stated"),
        Node(id="n2", label="Aunt Susan", type="Person", source="user-stated"),
        Node(id="n3", label="drained", type="EnergyState", source="ai-inferred"),
    )
    edges = (
        Edge(
            source_id="n2",
            target_id="n3",
            relationship="DRAINS",
            confidence=0.9,
        ),
    )
    return Graph(nodes=nodes, edges=edges)


@pytest.fixture
def empty_graph() -> Graph:
    """Create an empty graph for testing."""
    return Graph(nodes=(), edges=())


@pytest.fixture
def single_node_graph() -> Graph:
    """Create a graph with only one node."""
    nodes = (Node(id="n1", label="Maya", type="Person", source="user-stated"),)
    return Graph(nodes=nodes, edges=())


class TestRenderHtmlBasic:
    """Test basic HTML generation functionality (AC #4, #5)."""

    def test_render_html_returns_valid_html_structure(self, mock_graph: Graph) -> None:
        """HTML output has valid document structure."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert html.startswith("<!DOCTYPE html>"), "HTML must start with DOCTYPE"
        assert "<html" in html, "HTML must contain <html> tag"
        assert "</html>" in html, "HTML must have closing </html> tag"
        assert "<head>" in html, "HTML must have <head> section"
        assert "</head>" in html, "HTML must have closing </head> tag"
        assert "<body>" in html, "HTML must have <body> section"
        assert "</body>" in html, "HTML must have closing </body> tag"

    def test_render_html_contains_inline_css(self, mock_graph: Graph) -> None:
        """HTML contains inline CSS in <style> tag (no external stylesheets)."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "<style>" in html, "HTML must contain <style> tag"
        assert "</style>" in html, "HTML must have closing </style> tag"
        # Verify basic styling is present
        assert "body" in html or "font-family" in html, "CSS must include body styling"

    def test_render_html_is_self_contained(self, mock_graph: Graph) -> None:
        """HTML has no external dependencies (self-contained)."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        # No external URLs
        assert "http://" not in html, "HTML must not contain HTTP URLs"
        assert "https://" not in html, "HTML must not contain HTTPS URLs"
        # No external stylesheet links
        assert '<link rel="stylesheet"' not in html, "No external stylesheets"
        # No external script sources (check both quote types)
        assert 'src="' not in html.lower(), "No external scripts with double quotes"
        assert "src='" not in html.lower(), "No external scripts with single quotes"

    def test_render_html_contains_svg(self, mock_graph: Graph) -> None:
        """HTML contains SVG-based graph visualization."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "<svg" in html, "HTML must contain SVG element"
        assert "</svg>" in html, "HTML must have closing SVG tag"

    def test_render_html_includes_node_labels(self, mock_graph: Graph) -> None:
        """HTML displays node labels in visualization."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "Maya" in html, "Node label 'Maya' must appear in HTML"
        assert "Aunt Susan" in html, "Node label 'Aunt Susan' must appear in HTML"
        assert "drained" in html, "Node label 'drained' must appear in HTML"

    def test_render_html_includes_edge_labels(self, mock_graph: Graph) -> None:
        """HTML displays edge relationship labels."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "DRAINS" in html, "Edge relationship 'DRAINS' must appear in HTML"


class TestRenderHtmlNodeStyling:
    """Test node source distinction in styling (AC #5)."""

    def test_render_html_distinguishes_node_sources_in_css(self, mock_graph: Graph) -> None:
        """CSS includes distinct styles for user-stated vs AI-inferred nodes."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        # Check for user-stated styling class or style
        has_user_style = "user-stated" in html or "user_stated" in html or "#4CAF50" in html
        # Check for ai-inferred styling class or style
        has_ai_style = "ai-inferred" in html or "ai_inferred" in html or "#9E9E9E" in html

        assert has_user_style, "HTML must have styling for user-stated nodes"
        assert has_ai_style, "HTML must have styling for AI-inferred nodes"


class TestRenderHtmlEmptyStates:
    """Test edge case handling for empty and minimal graphs."""

    def test_render_html_handles_empty_graph(self, empty_graph: Graph) -> None:
        """Empty graph returns valid HTML with appropriate message."""
        from sentinel.viz.html import render_html

        html = render_html(empty_graph)

        assert "<!DOCTYPE html>" in html, "Empty graph still returns valid HTML"
        # Should indicate no data
        assert "No" in html or "empty" in html.lower() or "no data" in html.lower(), (
            "Empty graph should indicate no data available"
        )

    def test_render_html_handles_single_node(self, single_node_graph: Graph) -> None:
        """Single node graph renders correctly."""
        from sentinel.viz.html import render_html

        html = render_html(single_node_graph)

        assert "<!DOCTYPE html>" in html, "Single node graph returns valid HTML"
        assert "Maya" in html, "Single node label appears in output"
        assert "<svg" in html, "SVG is still generated for single node"


class TestRenderHtmlCollisionHighlighting:
    """Test collision path highlighting (AC #6)."""

    @pytest.fixture
    def collision_graph(self) -> Graph:
        """Create a graph with collision-relevant structure."""
        nodes = (
            Node(id="n1", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="n2", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="n3", label="Work Meeting", type="Activity", source="user-stated"),
            Node(id="n4", label="High Focus", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="DRAINS",
                confidence=0.9,
            ),
            Edge(
                source_id="n2",
                target_id="n3",
                relationship="CONFLICTS_WITH",
                confidence=0.8,
            ),
            Edge(
                source_id="n3",
                target_id="n4",
                relationship="REQUIRES",
                confidence=0.85,
            ),
        )
        return Graph(nodes=nodes, edges=edges)

    def test_render_html_highlights_collision_paths(self, collision_graph: Graph) -> None:
        """Collision paths are marked with collision CSS class."""
        from sentinel.viz.html import render_html

        collision_paths = [("Aunt Susan", "DRAINS", "drained")]
        html = render_html(collision_graph, collision_paths=collision_paths)

        # Collision nodes should have collision class
        assert "collision" in html, "Collision paths should be marked with collision class"

    def test_render_html_collision_styling_present(self, collision_graph: Graph) -> None:
        """Collision elements have distinct visual styling (red color)."""
        from sentinel.viz.html import render_html

        collision_paths = [("Aunt Susan", "DRAINS", "drained")]
        html = render_html(collision_graph, collision_paths=collision_paths)

        # Red color (#F44336) should be used for collision elements
        assert "#F44336" in html, "Collision elements should use red color"

    def test_render_html_edges_get_collision_highlight_class(self, collision_graph: Graph) -> None:
        """Edges in collision paths get collision-highlight class (AC#6)."""
        from sentinel.viz.html import render_html

        collision_paths = [("Aunt Susan", "DRAINS", "drained")]
        html = render_html(collision_graph, collision_paths=collision_paths)

        # Edge elements in collision path should have collision-highlight class
        assert 'class="edge collision-highlight"' in html, (
            "Edges in collision paths must have collision-highlight class"
        )

    def test_render_html_no_collision_without_paths(self, mock_graph: Graph) -> None:
        """Without collision paths, no collision styling is applied."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph, collision_paths=None)

        # Should not have collision-highlight class applied to edge elements
        # (note: the CSS rule .edge.collision-highlight is always in the stylesheet)
        assert 'class="edge collision-highlight"' not in html, (
            "Without collision paths, edges should not have collision-highlight class"
        )
        # Should have normal edge class
        assert 'class="edge"' in html, "Edges should have edge class"
        # Should not have collision warning section
        assert '<section class="collisions">' not in html, (
            "Without collision paths, no collision section should appear"
        )

    def test_render_html_generates_collision_warning_cards(self, collision_graph: Graph) -> None:
        """Collision paths generate warning cards in HTML (AC#8)."""
        from sentinel.viz.html import render_html

        collision_paths = [("Aunt Susan", "DRAINS", "drained")]
        html = render_html(collision_graph, collision_paths=collision_paths)

        # Should have collision section with cards
        assert '<section class="collisions">' in html, "Should have collision warnings section"
        assert "Collision Warnings" in html, "Should have collision warnings heading"
        assert '<div class="collision-card">' in html, "Should have collision card"
        # Should show the path elements
        assert "Aunt Susan" in html, "Collision path should show entity"
        assert "DRAINS" in html, "Collision path should show relationship"

    def test_render_html_collision_path_with_missing_entity(self, collision_graph: Graph) -> None:
        """Collision path with entity not in graph is handled gracefully."""
        from sentinel.viz.html import render_html

        # Collision path references "Unknown Entity" which doesn't exist in graph
        collision_paths = [("Unknown Entity", "DRAINS", "Nonexistent Node")]
        html = render_html(collision_graph, collision_paths=collision_paths)

        # Should still render valid HTML without crashing
        assert "<!DOCTYPE html>" in html, "Should return valid HTML"
        assert "<svg" in html, "Should still render SVG graph"
        # The missing entities should just not be highlighted
        # (no crash, no collision class on edges that don't exist)


class TestRenderHtmlPerformance:
    """Test HTML rendering performance (AC #7)."""

    @pytest.fixture
    def large_graph(self) -> Graph:
        """Create a graph with 100 nodes for performance testing."""
        nodes = tuple(
            Node(
                id=f"n{i}",
                label=f"Entity{i}",
                type="Entity",
                source="user-stated" if i % 2 == 0 else "ai-inferred",
            )
            for i in range(100)
        )
        # Create edges connecting nodes in a chain with some branches
        edges = []
        for i in range(99):
            edges.append(
                Edge(
                    source_id=f"n{i}",
                    target_id=f"n{i + 1}",
                    relationship="CONNECTS",
                    confidence=0.9,
                )
            )
        return Graph(nodes=tuple(nodes), edges=tuple(edges))

    def test_render_html_completes_within_5_seconds(self, large_graph: Graph) -> None:
        """HTML export completes within 5 seconds (AC #7)."""
        import time

        from sentinel.viz.html import render_html

        start = time.time()
        html = render_html(large_graph)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"HTML export took {elapsed:.2f}s, expected < 5s"
        assert len(html) > 0, "HTML should not be empty"
        # Verify all nodes are in output
        assert "Entity0" in html, "First node should be in output"
        assert "Entity99" in html, "Last node should be in output"

    def test_render_html_with_collision_paths_performance(self, large_graph: Graph) -> None:
        """HTML export with collision highlighting completes within 5 seconds."""
        import time

        from sentinel.viz.html import render_html

        # Create collision paths
        collision_paths = [
            ("Entity0", "CONNECTS", "Entity1", "CONNECTS", "Entity2"),
            ("Entity50", "CONNECTS", "Entity51", "CONNECTS", "Entity52"),
        ]

        start = time.time()
        html = render_html(large_graph, collision_paths=collision_paths)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"HTML export with collisions took {elapsed:.2f}s, expected < 5s"
        assert "collision" in html, "HTML should have collision highlighting"


class TestRenderHtmlMetadata:
    """Test HTML metadata and structure."""

    def test_render_html_includes_title(self, mock_graph: Graph) -> None:
        """HTML includes a title element."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "<title>" in html, "HTML must have title element"
        assert "</title>" in html, "HTML must have closing title tag"
        assert "Sentinel" in html, "Title should mention Sentinel"

    def test_render_html_includes_charset(self, mock_graph: Graph) -> None:
        """HTML includes charset meta tag for proper encoding."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert 'charset="UTF-8"' in html or "charset=utf-8" in html.lower(), (
            "HTML must specify UTF-8 charset"
        )

    def test_render_html_includes_viewport(self, mock_graph: Graph) -> None:
        """HTML includes viewport meta tag for responsive design."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        assert "viewport" in html, "HTML should include viewport meta tag"

    def test_render_html_includes_legend(self, mock_graph: Graph) -> None:
        """HTML includes a legend explaining node styling."""
        from sentinel.viz.html import render_html

        html = render_html(mock_graph)

        # Legend should have proper structure with legend class
        assert '<div class="legend">' in html, "HTML should include legend div with proper class"
        # Should explain user-stated vs AI-inferred distinction
        assert "User-stated" in html, "Legend should explain User-stated nodes"
        assert "AI-inferred" in html, "Legend should explain AI-inferred nodes"
