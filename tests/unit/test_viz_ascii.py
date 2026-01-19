"""Unit tests for viz.ascii module.

Tests ASCII graph visualization with node styling and edge labels.
"""

from sentinel.core.types import Edge, Graph, Node


class TestVizModuleStructure:
    """Test viz module exists and exports correctly."""

    def test_viz_module_importable(self) -> None:
        """Verify viz module can be imported."""
        from sentinel import viz

        assert viz is not None

    def test_render_ascii_exported(self) -> None:
        """Verify render_ascii is exported from viz module."""
        from sentinel.viz import render_ascii

        assert callable(render_ascii)

    def test_graph_to_networkx_exported(self) -> None:
        """Verify graph_to_networkx is exported from viz module."""
        from sentinel.viz import graph_to_networkx

        assert callable(graph_to_networkx)


class TestGraphToNetworkX:
    """Test Graph-to-NetworkX conversion."""

    def test_graph_to_networkx_with_typical_graph(self) -> None:
        """Test conversion of typical graph with nodes and edges."""
        from sentinel.viz import graph_to_networkx

        nodes = (
            Node(id="n1", label="Alice", type="Person", source="user-stated"),
            Node(id="n2", label="Meeting", type="Activity", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="INVOLVES",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        nx_graph = graph_to_networkx(graph)

        assert len(nx_graph.nodes) == 2, f"Expected 2 nodes, got {len(nx_graph.nodes)}"
        assert len(nx_graph.edges) == 1, f"Expected 1 edge, got {len(nx_graph.edges)}"

    def test_graph_to_networkx_with_empty_graph(self) -> None:
        """Test conversion of empty graph returns empty DiGraph."""
        from sentinel.viz import graph_to_networkx

        graph = Graph(nodes=(), edges=())

        nx_graph = graph_to_networkx(graph)

        assert len(nx_graph.nodes) == 0, "Expected empty graph"
        assert len(nx_graph.edges) == 0, "Expected no edges"

    def test_graph_to_networkx_preserves_node_attributes(self) -> None:
        """Test that node attributes (original_id, source) are preserved."""
        from sentinel.viz import graph_to_networkx

        node = Node(id="n1", label="Test", type="Person", source="ai-inferred")
        graph = Graph(nodes=(node,), edges=())

        nx_graph = graph_to_networkx(graph)

        # Node ID is formatted label: (Test) for ai-inferred
        assert "(Test)" in nx_graph.nodes, f"Expected (Test), got {list(nx_graph.nodes)}"
        assert nx_graph.nodes["(Test)"]["source"] == "ai-inferred"
        assert nx_graph.nodes["(Test)"]["original_id"] == "n1"

    def test_graph_to_networkx_preserves_edge_attributes(self) -> None:
        """Test that edge relationship labels are preserved."""
        from sentinel.viz import graph_to_networkx

        nodes = (
            Node(id="n1", label="A", type="Person", source="user-stated"),
            Node(id="n2", label="B", type="Activity", source="user-stated"),
        )
        edge = Edge(
            source_id="n1",
            target_id="n2",
            relationship="DRAINS",
            confidence=0.8,
        )
        graph = Graph(nodes=nodes, edges=(edge,))

        nx_graph = graph_to_networkx(graph)

        # Edges use formatted labels: [A] and [B] for user-stated
        assert nx_graph.edges["[A]", "[B]"]["label"] == "DRAINS"


class TestRenderAscii:
    """Test ASCII rendering functionality."""

    def test_render_ascii_produces_output(self) -> None:
        """Test that render_ascii produces non-empty string."""
        from sentinel.viz import render_ascii

        nodes = (
            Node(id="n1", label="Alice", type="Person", source="user-stated"),
            Node(id="n2", label="drained", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="DRAINS",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = render_ascii(graph)

        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 0, "Expected non-empty output"

    def test_render_ascii_empty_graph_returns_friendly_message(self) -> None:
        """Test empty graph returns friendly message, not exception."""
        from sentinel.viz import render_ascii

        graph = Graph(nodes=(), edges=())

        result = render_ascii(graph)

        assert "No entities found" in result, f"Expected friendly message, got: {result}"


class TestNodeStyling:
    """Test visual distinction of node sources."""

    def test_user_stated_nodes_have_square_brackets(self) -> None:
        """Test user-stated nodes use square brackets."""
        from sentinel.viz import render_ascii

        node = Node(id="n1", label="Alice", type="Person", source="user-stated")
        graph = Graph(nodes=(node,), edges=())

        result = render_ascii(graph)

        assert "[Alice]" in result, f"Expected [Alice] for user-stated, got: {result}"

    def test_ai_inferred_nodes_have_parentheses(self) -> None:
        """Test AI-inferred nodes use parentheses."""
        from sentinel.viz import render_ascii

        node = Node(id="n1", label="drained", type="EnergyState", source="ai-inferred")
        graph = Graph(nodes=(node,), edges=())

        result = render_ascii(graph)

        assert "(drained)" in result, f"Expected (drained) for ai-inferred, got: {result}"


class TestErrorHandling:
    """Test error handling in render_ascii."""

    def test_render_ascii_handles_phart_exception(self) -> None:
        """Test that phart exceptions are caught and return friendly message."""
        from unittest.mock import patch

        from sentinel.core.types import Graph, Node
        from sentinel.viz import render_ascii

        node = Node(id="n1", label="Test", type="Person", source="user-stated")
        graph = Graph(nodes=(node,), edges=())

        # Mock ASCIIRenderer to raise an exception
        with patch("sentinel.viz.ascii.ASCIIRenderer") as mock_renderer:
            mock_renderer.side_effect = RuntimeError("phart crash")
            result = render_ascii(graph)

        assert "Could not render" in result, f"Expected error message, got: {result}"

    def test_render_ascii_warns_on_large_graph(self) -> None:
        """Test that large graphs (>50 nodes) show a warning."""
        from sentinel.core.types import Graph, Node
        from sentinel.viz import render_ascii

        # Create 51 nodes to trigger warning
        nodes = tuple(
            Node(id=f"n{i}", label=f"Node{i}", type="Activity", source="user-stated")
            for i in range(51)
        )
        graph = Graph(nodes=nodes, edges=())

        result = render_ascii(graph)

        assert "Large graph detected" in result, f"Expected large graph warning, got: {result}"
        assert "51 nodes" in result, f"Expected node count in warning, got: {result}"


class TestEdgeDeduplication:
    """Test edge deduplication in relationships section."""

    def test_duplicate_edges_are_deduplicated(self) -> None:
        """Test that duplicate edges only appear once in Relationships."""
        from sentinel.core.types import Edge, Graph, Node
        from sentinel.viz import render_ascii

        nodes = (
            Node(id="n1", label="Alice", type="Person", source="user-stated"),
            Node(id="n2", label="Bob", type="Person", source="user-stated"),
        )
        # Same edge twice
        edges = (
            Edge(source_id="n1", target_id="n2", relationship="KNOWS", confidence=0.9),
            Edge(source_id="n1", target_id="n2", relationship="KNOWS", confidence=0.8),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = render_ascii(graph)

        # Count occurrences of the relationship line
        count = result.count("[Alice] --KNOWS--> [Bob]")
        assert count == 1, f"Expected 1 occurrence of edge, got {count}. Result:\n{result}"


class TestDanglingEdges:
    """Test handling of edges referencing non-existent nodes."""

    def test_graph_to_networkx_handles_dangling_edge(self) -> None:
        """Test that edges referencing missing nodes use raw IDs as fallback."""
        from sentinel.viz import graph_to_networkx

        nodes = (Node(id="n1", label="Alice", type="Person", source="user-stated"),)
        # Edge references n2 which doesn't exist
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",  # Dangling reference
                relationship="KNOWS",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        nx_graph = graph_to_networkx(graph)

        # Should have 2 nodes: [Alice] and raw "n2" as fallback
        assert len(nx_graph.nodes) == 2, f"Expected 2 nodes, got {len(nx_graph.nodes)}"
        assert "[Alice]" in nx_graph.nodes, "Expected formatted node [Alice]"
        assert "n2" in nx_graph.nodes, "Expected raw fallback node n2"

    def test_render_ascii_handles_dangling_edge(self) -> None:
        """Test render_ascii produces output even with dangling edges."""
        from sentinel.viz import render_ascii

        nodes = (Node(id="n1", label="Alice", type="Person", source="user-stated"),)
        edges = (
            Edge(
                source_id="n1",
                target_id="missing",  # Dangling reference
                relationship="REFERS_TO",
                confidence=0.8,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = render_ascii(graph)

        assert "[Alice]" in result, f"Expected [Alice], got: {result}"
        assert "REFERS_TO" in result, f"Expected REFERS_TO relationship, got: {result}"


class TestEdgeLabels:
    """Test edge relationship labels in output."""

    def test_edge_labels_included_in_output(self) -> None:
        """Test that edge relationship types appear in Relationships section."""
        from sentinel.viz import render_ascii

        nodes = (
            Node(id="n1", label="Alice", type="Person", source="user-stated"),
            Node(id="n2", label="drained", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="DRAINS",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = render_ascii(graph)

        assert "DRAINS" in result, f"Expected DRAINS label, got: {result}"
        assert "Relationships:" in result, f"Expected Relationships section, got: {result}"

    def test_edge_labels_show_arrow_notation(self) -> None:
        """Test that relationships use --LABEL--> arrow notation."""
        from sentinel.viz import render_ascii

        nodes = (
            Node(id="n1", label="Alice", type="Person", source="user-stated"),
            Node(id="n2", label="drained", type="EnergyState", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="DRAINS",
                confidence=0.9,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        result = render_ascii(graph)

        assert "--DRAINS-->" in result, f"Expected --DRAINS-->, got: {result}"
