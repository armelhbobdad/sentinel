"""Unit tests for CLI display functions.

Tests for collision display formatting, path rendering, and temporal context.
Story 2.3: Warning Display with Path Explanation.
"""

import pytest

from sentinel.core.types import Edge, Graph, Node, ScoredCollision


class TestFormatCollisionPath:
    """Tests for format_collision_path function."""

    def test_format_collision_path_basic(self) -> None:
        """Test formatting a basic collision path."""
        from sentinel.cli.commands import format_collision_path

        collision = ScoredCollision(
            path=(
                "Aunt Susan",
                "DRAINS",
                "Low Energy",
                "CONFLICTS_WITH",
                "High Focus Required",
                "REQUIRES",
                "Strategy Presentation",
            ),
            confidence=0.75,
            source_breakdown={"ai_inferred": 2, "user_stated": 2},
        )

        result = format_collision_path(collision)

        # Entities should be bold, relationships should be dim
        assert "[bold]" in result, "Expected [bold] markup for entities"
        assert "[dim]" in result, "Expected [dim] markup for relationships"
        assert "→" in result, "Expected arrow separators between path elements"
        assert "Aunt Susan" in result, "Expected source entity in formatted path"
        assert "Strategy Presentation" in result, "Expected target entity in formatted path"

    def test_format_collision_path_with_domain_labels(self) -> None:
        """Test formatting path with domain labels like [SOCIAL]."""
        from sentinel.cli.commands import format_collision_path

        collision = ScoredCollision(
            path=(
                "[SOCIAL] Aunt Susan",
                "DRAINS",
                "Low Energy",
                "CONFLICTS_WITH",
                "High Focus Required",
                "REQUIRES",
                "[PROFESSIONAL] Strategy Presentation",
            ),
            confidence=0.82,
            source_breakdown={"ai_inferred": 2, "user_stated": 2},
        )

        result = format_collision_path(collision)

        # Domain labels should be escaped so they don't disappear as Rich styles
        # The actual brackets should appear in output
        assert "SOCIAL" in result, "Expected SOCIAL domain label in output"
        assert "PROFESSIONAL" in result, "Expected PROFESSIONAL domain label in output"
        assert "Aunt Susan" in result, "Expected entity name in output"
        assert "Strategy Presentation" in result, "Expected target entity in output"

    def test_format_collision_path_escapes_brackets(self) -> None:
        """Test that brackets in labels are escaped for Rich markup safety."""
        from sentinel.cli.commands import format_collision_path

        # Path with brackets that could be misinterpreted as Rich styles
        collision = ScoredCollision(
            path=(
                "[Meeting] Team Sync",
                "DRAINS",
                "Energy",
            ),
            confidence=0.6,
            source_breakdown={},
        )

        result = format_collision_path(collision)

        # The word "Meeting" should appear (not disappear as invalid style)
        assert "Meeting" in result, "Bracket content should be escaped, not rendered as style"
        assert "Team Sync" in result, "Entity name should appear in output"

    def test_format_collision_path_alternating_styles(self) -> None:
        """Test that entities and relationships have alternating styles."""
        from sentinel.cli.commands import format_collision_path

        collision = ScoredCollision(
            path=(
                "Entity1",  # index 0 - entity (bold)
                "REL1",  # index 1 - relationship (dim)
                "Entity2",  # index 2 - entity (bold)
                "REL2",  # index 3 - relationship (dim)
                "Entity3",  # index 4 - entity (bold)
            ),
            confidence=0.7,
            source_breakdown={},
        )

        result = format_collision_path(collision)

        # Count style applications
        bold_count = result.count("[bold]")
        dim_count = result.count("[dim]")

        # Should have 3 bold (entities) and 2 dim (relationships)
        assert bold_count == 3, f"Expected 3 bold, got {bold_count}"
        assert dim_count == 2, f"Expected 2 dim, got {dim_count}"

    def test_format_collision_path_short_path(self) -> None:
        """Test formatting a minimal path."""
        from sentinel.cli.commands import format_collision_path

        collision = ScoredCollision(
            path=("Source", "EDGE", "Target"),
            confidence=0.5,
            source_breakdown={},
        )

        result = format_collision_path(collision)

        assert "Source" in result, "Expected source entity in path"
        assert "EDGE" in result, "Expected relationship in path"
        assert "Target" in result, "Expected target entity in path"
        assert "→" in result, "Expected arrow separator"


class TestExtractTemporalContext:
    """Tests for extract_temporal_context function."""

    def test_extract_temporal_context_with_days(self) -> None:
        """Test extraction when nodes have day metadata."""
        from sentinel.cli.commands import extract_temporal_context

        nodes = (
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
                metadata={},
            ),
            Node(
                id="activity-presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
                metadata={"day": "Monday"},
            ),
        )
        edges = (
            Edge(
                source_id="activity-dinner",
                target_id="energy-low",
                relationship="DRAINS",
                confidence=0.8,
                metadata={},
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        collision = ScoredCollision(
            path=(
                "Dinner with Aunt Susan",
                "DRAINS",
                "Low Energy",
                "CONFLICTS_WITH",
                "High Focus Required",
                "REQUIRES",
                "Strategy Presentation",
            ),
            confidence=0.75,
            source_breakdown={},
        )

        result = extract_temporal_context(collision, graph)

        # Should mention both days
        assert result is not None, "Expected temporal context when nodes have day metadata"
        assert "Sunday" in result or "Monday" in result, (
            f"Expected day reference in temporal context: {result}"
        )

    def test_extract_temporal_context_no_temporal_data(self) -> None:
        """Test extraction returns None when no temporal data."""
        from sentinel.cli.commands import extract_temporal_context

        nodes = (
            Node(
                id="person-bob",
                label="Bob",
                type="Person",
                source="user-stated",
                metadata={},  # No temporal data
            ),
            Node(
                id="activity-task",
                label="Task",
                type="Activity",
                source="user-stated",
                metadata={},  # No temporal data
            ),
        )
        graph = Graph(nodes=nodes, edges=())

        collision = ScoredCollision(
            path=("Bob", "DRAINS", "Energy", "REQUIRES", "Task"),
            confidence=0.6,
            source_breakdown={},
        )

        result = extract_temporal_context(collision, graph)

        # Should return None when no temporal data available
        assert result is None, "Expected None when nodes have no temporal metadata"

    def test_extract_temporal_context_with_domain_labels(self) -> None:
        """Test extraction handles domain-prefixed labels in path."""
        from sentinel.cli.commands import extract_temporal_context

        nodes = (
            Node(
                id="person-aunt",
                label="Aunt Susan",  # Note: no domain prefix in actual node
                type="Person",
                source="user-stated",
                metadata={"day": "Sunday"},
            ),
            Node(
                id="activity-pres",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
                metadata={"day": "Monday"},
            ),
        )
        graph = Graph(nodes=nodes, edges=())

        # Path has domain labels but graph nodes don't
        collision = ScoredCollision(
            path=(
                "[SOCIAL] Aunt Susan",  # Domain prefix in path
                "DRAINS",
                "Low Energy",
                "REQUIRES",
                "[PROFESSIONAL] Strategy Presentation",  # Domain prefix in path
            ),
            confidence=0.8,
            source_breakdown={},
        )

        result = extract_temporal_context(collision, graph)

        # Should find temporal data by stripping domain prefixes from path labels
        assert result is not None, (
            "Expected temporal context when nodes have day metadata and path has domain prefixes"
        )
        assert "Sunday" in result or "Monday" in result, (
            f"Expected day reference in temporal context: {result}"
        )


class TestDisplayCollisionWarning:
    """Tests for display_collision_warning function."""

    def test_display_collision_warning_high_confidence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test display shows COLLISION DETECTED for high confidence."""
        from io import StringIO

        from rich.console import Console

        from sentinel.cli.commands import display_collision_warning

        # Create test collision with high confidence
        collision = ScoredCollision(
            path=(
                "[SOCIAL] Aunt Susan",
                "DRAINS",
                "Low Energy",
                "CONFLICTS_WITH",
                "High Focus Required",
                "REQUIRES",
                "[PROFESSIONAL] Strategy Presentation",
            ),
            confidence=0.85,
            source_breakdown={"ai_inferred": 2, "user_stated": 2},
        )

        graph = Graph(
            nodes=(
                Node(
                    id="person-aunt",
                    label="Aunt Susan",
                    type="Person",
                    source="user-stated",
                    metadata={"day": "Sunday"},
                ),
                Node(
                    id="activity-pres",
                    label="Strategy Presentation",
                    type="Activity",
                    source="user-stated",
                    metadata={"day": "Monday"},
                ),
            ),
            edges=(),
        )

        # Capture to StringIO
        output = StringIO()
        test_console = Console(file=output, force_terminal=True)

        display_collision_warning(collision, 1, graph, target_console=test_console)

        result = output.getvalue()
        assert "COLLISION DETECTED" in result, (
            "Expected 'COLLISION DETECTED' header for high confidence collision"
        )
        assert "85%" in result, "Expected confidence percentage in output"

    def test_display_collision_warning_medium_confidence(self) -> None:
        """Test display shows POTENTIAL RISK for medium confidence."""
        from io import StringIO

        from rich.console import Console

        from sentinel.cli.commands import display_collision_warning

        collision = ScoredCollision(
            path=("Source", "DRAINS", "Target"),
            confidence=0.65,
            source_breakdown={},
        )

        graph = Graph(nodes=(), edges=())

        output = StringIO()
        test_console = Console(file=output, force_terminal=True)

        display_collision_warning(collision, 1, graph, target_console=test_console)

        result = output.getvalue()
        assert "POTENTIAL RISK" in result, (
            "Expected 'POTENTIAL RISK' header for medium confidence collision"
        )

    def test_display_collision_warning_shows_path(self) -> None:
        """Test display includes the formatted collision path."""
        from io import StringIO

        from rich.console import Console

        from sentinel.cli.commands import display_collision_warning

        collision = ScoredCollision(
            path=("Entity A", "REL1", "Entity B"),
            confidence=0.7,
            source_breakdown={},
        )

        graph = Graph(nodes=(), edges=())

        output = StringIO()
        test_console = Console(file=output, force_terminal=True)

        display_collision_warning(collision, 1, graph, target_console=test_console)

        result = output.getvalue()
        assert "Entity A" in result
        assert "Entity B" in result


class TestRenderAsciiWithCollisionHighlight:
    """Tests for render_ascii collision path highlighting."""

    def test_render_ascii_highlights_collision_nodes(self) -> None:
        """Test that collision path nodes get >> prefix."""
        from sentinel.viz.ascii import render_ascii

        nodes = (
            Node(id="n1", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="n2", label="Low Energy", type="EnergyState", source="ai-inferred"),
            Node(id="n3", label="Strategy Presentation", type="Activity", source="user-stated"),
        )
        edges = (
            Edge(
                source_id="n1",
                target_id="n2",
                relationship="DRAINS",
                confidence=0.8,
                metadata={},
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        # Pass collision path with domain prefixes
        collision_paths = [
            (
                "[SOCIAL] Aunt Susan",
                "DRAINS",
                "Low Energy",
                "REQUIRES",
                "[PROFESSIONAL] Strategy Presentation",
            ),
        ]

        result = render_ascii(graph, collision_paths=collision_paths)

        # Highlighted nodes should have >> prefix
        assert ">> [Aunt Susan]" in result
        assert ">> (Low Energy)" in result
        assert ">> [Strategy Presentation]" in result

    def test_render_ascii_no_highlight_without_collision_paths(self) -> None:
        """Test that nodes without collision paths don't get highlight."""
        from sentinel.viz.ascii import render_ascii

        nodes = (Node(id="n1", label="Activity", type="Activity", source="user-stated"),)
        graph = Graph(nodes=nodes, edges=())

        result = render_ascii(graph)

        # Should not have >> prefix
        assert ">>" not in result
        assert "[Activity]" in result


class TestGetConfidenceLevel:
    """Tests for confidence level classification."""

    def test_high_confidence(self) -> None:
        """Test HIGH confidence at threshold."""
        from sentinel.cli.commands import get_confidence_level

        assert get_confidence_level(0.8) == "HIGH"
        assert get_confidence_level(0.9) == "HIGH"
        assert get_confidence_level(1.0) == "HIGH"

    def test_medium_confidence(self) -> None:
        """Test MEDIUM confidence range."""
        from sentinel.cli.commands import get_confidence_level

        assert get_confidence_level(0.5) == "MEDIUM"
        assert get_confidence_level(0.6) == "MEDIUM"
        assert get_confidence_level(0.79) == "MEDIUM"

    def test_low_confidence(self) -> None:
        """Test LOW confidence below threshold."""
        from sentinel.cli.commands import get_confidence_level

        assert get_confidence_level(0.49) == "LOW"
        assert get_confidence_level(0.3) == "LOW"
        assert get_confidence_level(0.0) == "LOW"
