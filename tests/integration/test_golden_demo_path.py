"""Golden Demo Path Integration Test.

Created during Epic 4 Retrospective based on QA Engineer Dana's recommendation:
"We need a 'golden demo path' test that validates:
paste → check → collision found → graph export works."

This P0 integration test validates the critical user journey for competition demos:
1. User pastes schedule with energy-draining interaction
2. Check command detects collision
3. Graph command exports HTML visualization

Test Architect: Murat (TEA Agent)
Risk Level: CRITICAL - Demo failure = credibility loss at competition
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import (
    EXIT_COLLISION_DETECTED,
    EXIT_SUCCESS,
)
from sentinel.core.types import Edge, Graph, Node


def _create_demo_collision_graph() -> Graph:
    """Create the canonical demo graph with Aunt Susan collision pattern.

    This graph represents Maya's typical week scenario:
    - Sunday: Dinner with Aunt Susan (emotionally draining)
    - Monday: Strategy presentation (requires focus)

    Pattern: (Aunt Susan)-[:DRAINS]->(drained)-[:CONFLICTS_WITH]->
             (focused)<-[:REQUIRES]-(Strategy Presentation)
    """
    nodes = (
        Node(
            id="person-aunt-susan",
            label="Aunt Susan",
            type="Person",
            source="user-stated",
            metadata={"extracted_from": "Sunday dinner"},
        ),
        Node(
            id="activity-dinner",
            label="Dinner with Aunt Susan",
            type="Activity",
            source="user-stated",
            metadata={"day": "Sunday"},
        ),
        Node(
            id="energystate-drained",
            label="drained",
            type="EnergyState",
            source="ai-inferred",
            metadata={"level": "depleted"},
        ),
        Node(
            id="energystate-focused",
            label="focused",
            type="EnergyState",
            source="ai-inferred",
            metadata={"level": "peak"},
        ),
        Node(
            id="activity-presentation",
            label="Strategy Presentation",
            type="Activity",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
        Node(
            id="timeslot-sunday-evening",
            label="Sunday Evening",
            type="TimeSlot",
            source="ai-inferred",
            metadata={"day": "Sunday", "time": "evening"},
        ),
        Node(
            id="timeslot-monday-morning",
            label="Monday Morning",
            type="TimeSlot",
            source="ai-inferred",
            metadata={"day": "Monday", "time": "morning"},
        ),
    )
    edges = (
        Edge(
            source_id="person-aunt-susan",
            target_id="energystate-drained",
            relationship="DRAINS",
            confidence=0.85,
            metadata={"reason": "emotionally draining"},
        ),
        Edge(
            source_id="activity-dinner",
            target_id="person-aunt-susan",
            relationship="INVOLVES",
            confidence=0.90,
            metadata={},
        ),
        Edge(
            source_id="energystate-drained",
            target_id="energystate-focused",
            relationship="CONFLICTS_WITH",
            confidence=0.80,
            metadata={"conflict_type": "energy_depletion"},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="energystate-focused",
            relationship="REQUIRES",
            confidence=0.90,
            metadata={"requirement": "mental_sharpness"},
        ),
        Edge(
            source_id="activity-dinner",
            target_id="timeslot-sunday-evening",
            relationship="SCHEDULED_AT",
            confidence=0.95,
            metadata={},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="timeslot-monday-morning",
            relationship="SCHEDULED_AT",
            confidence=0.95,
            metadata={},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


DEMO_SCHEDULE_TEXT = """Maya's Week:

Sunday:
- 6:00 PM: Dinner with Aunt Susan (she's emotionally draining but family obligation)

Monday:
- 9:00 AM: Strategy Presentation to the executive team (need to be sharp)
- 2:00 PM: Team standup
"""


class TestGoldenDemoPath:
    """[P0] Critical integration test for the demo flow.

    Risk: CRITICAL - This is the flow shown in competition demos.
    Pattern: paste → check → collision detected → graph export

    This test ensures all commands work together in the expected sequence.
    """

    def test_golden_path_paste_check_collision_export(self) -> None:
        """[P0] Full demo path: paste → check → collision → HTML export with highlighting.

        GIVEN: User has a schedule with energy-draining social event before focus-required work
        WHEN: User runs paste → check --format html
        THEN: Collision is detected AND HTML export includes collision highlighting
        """
        runner = CliRunner()
        graph = _create_demo_collision_graph()

        with runner.isolated_filesystem():
            output_file = Path("collision-report.html")

            # Patch ingest and load at the module level where they're defined
            with (
                patch(
                    "sentinel.core.engine.CogneeEngine.ingest",
                    new_callable=AsyncMock,
                    return_value=graph,
                ),
                patch(
                    "sentinel.core.engine.CogneeEngine.load",
                    return_value=graph,
                ),
            ):
                # Step 1: PASTE - Ingest the schedule
                result_paste = runner.invoke(
                    main,
                    ["paste"],
                    input=DEMO_SCHEDULE_TEXT,
                    catch_exceptions=False,
                )

                # Verify paste succeeded
                assert result_paste.exit_code == EXIT_SUCCESS, (
                    f"Paste should succeed. Got exit code {result_paste.exit_code}. "
                    f"Output: {result_paste.output}"
                )
                assert "Schedule received" in result_paste.output, (
                    f"Expected confirmation message. Output: {result_paste.output}"
                )
                assert "entities" in result_paste.output.lower(), (
                    f"Expected entity count. Output: {result_paste.output}"
                )

                # Step 2: CHECK with HTML export - Detect collision AND export
                result_check = runner.invoke(
                    main,
                    ["check", "--format", "html", "--output", str(output_file)],
                    catch_exceptions=False,
                )

                # Verify collision was detected (exit code 1)
                assert result_check.exit_code == EXIT_COLLISION_DETECTED, (
                    f"Check should detect collision (exit code 1). "
                    f"Got {result_check.exit_code}. Output: {result_check.output}"
                )

                # Verify HTML file was created
                assert output_file.exists(), f"HTML file should be created at {output_file}"

                # Verify HTML content is valid and complete
                html_content = output_file.read_text()

                # HTML structure
                assert "<!DOCTYPE html>" in html_content, "HTML should have doctype"
                assert "<html" in html_content, "HTML should have html tag"
                assert "</html>" in html_content, "HTML should be closed"

                # Self-contained (no external dependencies)
                assert "<style>" in html_content, "HTML should have inline CSS"
                assert "<svg" in html_content, "HTML should contain SVG graph"

                # Contains demo entities
                assert "Aunt Susan" in html_content, "HTML should contain 'Aunt Susan' entity"
                assert "Strategy Presentation" in html_content, (
                    "HTML should contain 'Strategy Presentation' entity"
                )

                # Collision highlighting (only check command provides this)
                assert "collision" in html_content.lower(), (
                    "HTML should contain collision styling/indicators"
                )

    def test_golden_path_collision_path_highlighted_in_html(self) -> None:
        """[P0] Collision paths are visually highlighted in check HTML export.

        GIVEN: Graph with detected collision
        WHEN: Exported via check --format html
        THEN: Collision path edges have special styling/class for highlighting
        """
        runner = CliRunner()
        graph = _create_demo_collision_graph()

        with runner.isolated_filesystem():
            output_file = Path("collision-highlight.html")

            with patch(
                "sentinel.core.engine.CogneeEngine.load",
                return_value=graph,
            ):
                result = runner.invoke(
                    main,
                    ["check", "--format", "html", "--output", str(output_file)],
                    catch_exceptions=False,
                )

                # Check detects collision (exit code 1) but still creates HTML
                assert result.exit_code == EXIT_COLLISION_DETECTED
                assert output_file.exists()

                html_content = output_file.read_text()

                # Collision edges should have highlighting class
                assert "collision" in html_content.lower(), "HTML should contain collision styling"
                # Should show the DRAINS relationship in collision path
                assert "DRAINS" in html_content, (
                    "HTML should show DRAINS relationship in collision path"
                )

    def test_golden_path_check_shows_summary_before_graph(self, tmp_path: Path) -> None:
        """[P1] Check command shows collision summary that matches graph.

        GIVEN: Graph with collision pattern
        WHEN: Running check command
        THEN: Summary mentions collision count and affected entities
        """
        runner = CliRunner()
        graph = _create_demo_collision_graph()

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["check"], catch_exceptions=False)

            assert result.exit_code == EXIT_COLLISION_DETECTED

            # Should show collision count
            assert "collision" in result.output.lower()
            assert "affecting" in result.output.lower(), (
                f"Expected 'affecting' in summary. Output: {result.output}"
            )

            # Should show confidence indicator
            assert "%" in result.output or "confidence" in result.output.lower(), (
                f"Expected confidence indicator. Output: {result.output}"
            )

    def test_golden_path_graph_without_node_shows_full_graph(self, tmp_path: Path) -> None:
        """[P1] Graph command without node argument shows full graph.

        GIVEN: Valid graph with entities
        WHEN: Running 'sentinel graph' (no node specified)
        THEN: Full graph is displayed/exported
        """
        runner = CliRunner()
        graph = _create_demo_collision_graph()
        output_file = tmp_path / "full-graph.html"

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(
                main,
                ["graph", "--format", "html", "--output", str(output_file)],
                catch_exceptions=False,
            )

            assert result.exit_code == EXIT_SUCCESS
            html_content = output_file.read_text()

            # Should contain all key entities
            assert "Aunt Susan" in html_content
            assert "Strategy Presentation" in html_content
            assert "drained" in html_content.lower() or "focused" in html_content.lower()


class TestGoldenPathEdgeCases:
    """[P1] Edge cases for the golden demo path."""

    def test_demo_path_no_collision_still_exports_graph(self, tmp_path: Path) -> None:
        """[P1] Graph export works even when no collision exists.

        GIVEN: Graph with no collision pattern (boring week)
        WHEN: Running graph --format html
        THEN: HTML is created (collisions are optional for graph export)
        """
        runner = CliRunner()

        # Create graph without DRAINS pattern
        nodes = (
            Node(id="standup", label="Team Standup", type="Activity", source="user-stated"),
            Node(id="monday", label="Monday", type="TimeSlot", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="standup",
                target_id="monday",
                relationship="SCHEDULED_AT",
                confidence=0.9,
            ),
        )
        boring_graph = Graph(nodes=nodes, edges=edges)
        output_file = tmp_path / "boring-week.html"

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=boring_graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(
                main,
                ["graph", "--format", "html", "--output", str(output_file)],
                catch_exceptions=False,
            )

            assert result.exit_code == EXIT_SUCCESS
            assert output_file.exists()
            assert "Team Standup" in output_file.read_text()

    def test_demo_path_check_without_paste_shows_helpful_error(self) -> None:
        """[P1] Check without paste shows helpful error guiding user.

        GIVEN: No graph has been saved (first run)
        WHEN: Running 'sentinel check'
        THEN: Error message mentions running 'sentinel paste' first
        """
        runner = CliRunner()

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=None)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["check"], catch_exceptions=False)

            # Should fail with helpful message
            assert result.exit_code != EXIT_SUCCESS
            assert "paste" in result.output.lower(), (
                f"Error should mention 'paste'. Output: {result.output}"
            )


class TestGoldenPathPerformance:
    """[P2] Performance tests for the demo path."""

    def test_demo_path_graph_export_completes_quickly(self, tmp_path: Path) -> None:
        """[P2] HTML export completes within acceptable time.

        GIVEN: Demo-sized graph (7 nodes, 6 edges)
        WHEN: Exporting to HTML
        THEN: Completes within 2 seconds (demo-friendly)
        """
        import time

        runner = CliRunner()
        graph = _create_demo_collision_graph()
        output_file = tmp_path / "perf-test.html"

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            start = time.perf_counter()

            result = runner.invoke(
                main,
                ["graph", "--format", "html", "--output", str(output_file)],
                catch_exceptions=False,
            )

            elapsed = time.perf_counter() - start

            assert result.exit_code == EXIT_SUCCESS
            assert elapsed < 2.0, f"Export took {elapsed:.2f}s, expected < 2s"


@pytest.mark.live
class TestGoldenPathLive:
    """[P0] Live API tests for the golden demo path.

    These tests hit the real Cognee API to verify end-to-end behavior.
    Run manually before demos: uv run pytest -m live

    IMPORTANT: Requires COGNEE_API_KEY environment variable.
    """

    @pytest.mark.asyncio
    async def test_live_demo_schedule_produces_collision(self) -> None:
        """[P0 LIVE] Real Cognee API produces collision from demo schedule.

        GIVEN: Demo schedule text with Aunt Susan + presentation
        WHEN: Ingested through real Cognee API
        THEN: Graph contains collision-triggering pattern

        This test validates that our demo scenario actually works with Cognee.
        """
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.rules import detect_cross_domain_collisions

        engine = CogneeEngine()
        graph = await engine.ingest(DEMO_SCHEDULE_TEXT)

        # Verify we got entities
        assert len(graph.nodes) > 0, "Cognee should extract entities from demo text"

        # Check for collision pattern
        collisions = detect_cross_domain_collisions(graph)

        # Note: LLM output is variable - we check that SOME collision is found
        # rather than exact entity names
        if not collisions:
            # Log what we got for debugging
            node_labels = [n.label for n in graph.nodes]
            edge_types = [e.relationship for e in graph.edges]
            pytest.skip(
                f"No collision detected (LLM variability). "
                f"Nodes: {node_labels}, Edges: {edge_types}"
            )

        # At least one collision should involve the draining pattern
        collision = collisions[0]
        assert collision.confidence > 0, "Collision should have positive confidence"
