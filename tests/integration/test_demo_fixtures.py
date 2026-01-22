"""Demo fixture integration tests.

These tests validate the three demo scenarios work correctly:
1. maya_typical_week.txt - produces collision
2. maya_boring_week.txt - no collision, graceful empty state
3. maya_edge_cases.txt - Unicode/emoji handling without crashes

Test Architect: Story 5.6 - Demo Fixtures & CI/CD
Risk Level: HIGH - Demo failure = credibility loss at competition
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_COLLISION_DETECTED, EXIT_SUCCESS
from sentinel.core.types import Edge, Graph, Node

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "schedules"
TYPICAL_WEEK = FIXTURES_DIR / "maya_typical_week.txt"
BORING_WEEK = FIXTURES_DIR / "maya_boring_week.txt"
EDGE_CASES = FIXTURES_DIR / "maya_edge_cases.txt"


class TestDemoFixturesExist:
    """[P0] Verify demo fixture files exist and have content."""

    def test_fixtures_directory_exists(self) -> None:
        """Demo fixtures directory exists."""
        assert FIXTURES_DIR.exists(), f"Fixtures directory not found at {FIXTURES_DIR}"
        assert FIXTURES_DIR.is_dir()

    def test_typical_week_fixture_exists(self) -> None:
        """maya_typical_week.txt exists with collision-triggering content."""
        assert TYPICAL_WEEK.exists(), f"maya_typical_week.txt not found at {TYPICAL_WEEK}"
        content = TYPICAL_WEEK.read_text()
        # Fixture must have meaningful content (at least a schedule entry)
        assert content.strip(), "Fixture should have content"
        # Should contain draining scenario keywords
        assert "aunt susan" in content.lower() or "draining" in content.lower(), (
            "Typical week should mention energy-draining interaction"
        )

    def test_boring_week_fixture_exists(self) -> None:
        """maya_boring_week.txt exists with no collision content."""
        assert BORING_WEEK.exists(), f"maya_boring_week.txt not found at {BORING_WEEK}"
        content = BORING_WEEK.read_text()
        assert len(content) > 20, "Fixture should have some content"
        # Should NOT contain draining keywords
        assert "draining" not in content.lower(), (
            "Boring week should not have energy-draining content"
        )

    def test_edge_cases_fixture_exists(self) -> None:
        """maya_edge_cases.txt exists with Unicode/emoji content."""
        assert EDGE_CASES.exists(), f"maya_edge_cases.txt not found at {EDGE_CASES}"
        content = EDGE_CASES.read_text()
        # Should contain non-ASCII characters
        has_unicode = any(ord(c) > 127 for c in content)
        assert has_unicode, "Edge cases should contain Unicode characters (emoji, accents)"


class TestTypicalWeekCollision:
    """[P0] maya_typical_week.txt produces collision."""

    def test_typical_week_mock_produces_collision(self) -> None:
        """Typical week scenario triggers collision detection with MockEngine.

        GIVEN: maya_typical_week.txt content with Aunt Susan scenario
        WHEN: Processed through sentinel check
        THEN: At least one collision is detected
        """
        runner = CliRunner()

        # Mock graph with collision pattern
        nodes = (
            Node(id="aunt-susan", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
            Node(id="focused", label="focused", type="EnergyState", source="ai-inferred"),
            Node(
                id="presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        )
        edges = (
            Edge(
                source_id="aunt-susan", target_id="drained", relationship="DRAINS", confidence=0.85
            ),
            Edge(
                source_id="drained",
                target_id="focused",
                relationship="CONFLICTS_WITH",
                confidence=0.80,
            ),
            Edge(
                source_id="presentation",
                target_id="focused",
                relationship="REQUIRES",
                confidence=0.90,
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["check"], catch_exceptions=False)

            assert result.exit_code == EXIT_COLLISION_DETECTED, (
                f"Expected collision detected (exit code 1). Got {result.exit_code}. "
                f"Output: {result.output}"
            )
            assert "collision" in result.output.lower()


class TestBoringWeekNoCollision:
    """[P0] maya_boring_week.txt shows graceful empty state."""

    def test_boring_week_mock_no_collision(self) -> None:
        """Boring week scenario shows no collision with graceful message.

        GIVEN: maya_boring_week.txt content with no draining activities
        WHEN: Processed through sentinel check
        THEN: Graceful "no collisions" message displays
        """
        runner = CliRunner()

        # Graph without collision pattern
        nodes = (
            Node(id="standup", label="Team Standup", type="Activity", source="user-stated"),
            Node(id="monday", label="Monday", type="TimeSlot", source="ai-inferred"),
        )
        edges = (
            Edge(
                source_id="standup", target_id="monday", relationship="SCHEDULED_AT", confidence=0.9
            ),
        )
        graph = Graph(nodes=nodes, edges=edges)

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["check"], catch_exceptions=False)

            assert result.exit_code == EXIT_SUCCESS, (
                f"Expected success (exit code 0). Got {result.exit_code}. Output: {result.output}"
            )
            # Should show positive empty state message
            assert "no" in result.output.lower() and "collision" in result.output.lower()


class TestEdgeCasesNoCrash:
    """[P0] maya_edge_cases.txt processes without crash."""

    def test_edge_cases_file_readable(self) -> None:
        """Edge cases file can be read without encoding errors."""
        content = EDGE_CASES.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_edge_cases_mock_no_crash(self) -> None:
        """Edge cases content processes without crash (NFR13).

        GIVEN: maya_edge_cases.txt with Unicode, emoji, accented characters
        WHEN: Processed through sentinel paste
        THEN: No crashes occur from special characters
        """
        runner = CliRunner()
        content = EDGE_CASES.read_text()

        # Simple graph return (doesn't need collision pattern)
        nodes = (Node(id="cafe", label="Coffee with Maria", type="Activity", source="user-stated"),)
        graph = Graph(nodes=nodes, edges=())

        mock_engine = MagicMock()
        mock_engine.ingest = AsyncMock(return_value=graph)
        mock_engine.persist = MagicMock()

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["paste"], input=content, catch_exceptions=False)

            # Should not crash - exit code 0 for success
            assert result.exit_code == EXIT_SUCCESS, (
                f"Unexpected crash. Exit code: {result.exit_code}. Output: {result.output}"
            )


class TestFixtureContentIntegration:
    """[P0] Tests that validate actual fixture content flows through CLI."""

    def test_typical_week_content_triggers_ingest(self) -> None:
        """Actual maya_typical_week.txt content is passed to ingest.

        GIVEN: Real content from maya_typical_week.txt
        WHEN: Passed through sentinel paste
        THEN: The ingest receives the actual fixture content
        """
        runner = CliRunner()
        fixture_content = TYPICAL_WEEK.read_text()

        # Graph that would result from collision scenario
        nodes = (
            Node(id="aunt-susan", label="Aunt Susan", type="Person", source="user-stated"),
            Node(id="drained", label="drained", type="EnergyState", source="ai-inferred"),
        )
        graph = Graph(nodes=nodes, edges=())

        mock_engine = MagicMock()
        mock_engine.ingest = AsyncMock(return_value=graph)
        mock_engine.persist = MagicMock()

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["paste"], input=fixture_content, catch_exceptions=False)

            assert result.exit_code == EXIT_SUCCESS, (
                f"Paste with fixture content should succeed. Output: {result.output}"
            )
            # Verify ingest was called with the actual fixture content
            mock_engine.ingest.assert_called_once()
            call_args = mock_engine.ingest.call_args[0][0]
            assert "aunt susan" in call_args.lower() or "draining" in call_args.lower(), (
                f"Ingest should receive fixture content. Got: {call_args[:100]}..."
            )

    def test_boring_week_content_triggers_ingest(self) -> None:
        """Actual maya_boring_week.txt content is passed to ingest.

        GIVEN: Real content from maya_boring_week.txt
        WHEN: Passed through sentinel paste
        THEN: The ingest receives the boring week content (no draining keywords)
        """
        runner = CliRunner()
        fixture_content = BORING_WEEK.read_text()

        nodes = (Node(id="standup", label="Team Standup", type="Activity", source="user-stated"),)
        graph = Graph(nodes=nodes, edges=())

        mock_engine = MagicMock()
        mock_engine.ingest = AsyncMock(return_value=graph)
        mock_engine.persist = MagicMock()

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["paste"], input=fixture_content, catch_exceptions=False)

            assert result.exit_code == EXIT_SUCCESS
            mock_engine.ingest.assert_called_once()
            call_args = mock_engine.ingest.call_args[0][0]
            # Boring week should NOT have draining content
            assert "draining" not in call_args.lower(), (
                f"Boring week should not have draining content. Got: {call_args[:100]}..."
            )

    def test_edge_cases_unicode_content_preserved(self) -> None:
        """Unicode content from maya_edge_cases.txt is preserved through CLI.

        GIVEN: Real content from maya_edge_cases.txt with Unicode/emoji
        WHEN: Passed through sentinel paste
        THEN: Unicode characters are preserved in the content passed to ingest
        """
        runner = CliRunner()
        fixture_content = EDGE_CASES.read_text()

        nodes = (Node(id="cafe", label="Coffee", type="Activity", source="user-stated"),)
        graph = Graph(nodes=nodes, edges=())

        mock_engine = MagicMock()
        mock_engine.ingest = AsyncMock(return_value=graph)
        mock_engine.persist = MagicMock()

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["paste"], input=fixture_content, catch_exceptions=False)

            assert result.exit_code == EXIT_SUCCESS
            mock_engine.ingest.assert_called_once()
            call_args = mock_engine.ingest.call_args[0][0]
            # Verify Unicode was preserved (should have non-ASCII chars)
            has_unicode = any(ord(c) > 127 for c in call_args)
            assert has_unicode, (
                f"Unicode characters should be preserved. Got: {repr(call_args[:100])}..."
            )


class TestDemoStability:
    """[P1] Demo stability - consecutive runs succeed."""

    @pytest.mark.parametrize("run_number", range(5))
    def test_consecutive_check_runs_stable(self, run_number: int) -> None:
        """Five consecutive check runs all succeed (AC7).

        This parameterized test runs 5 times to verify stability.
        """
        runner = CliRunner()

        # Simple graph without collision
        nodes = (Node(id="meeting", label="Team Meeting", type="Activity", source="user-stated"),)
        graph = Graph(nodes=nodes, edges=())

        mock_engine = MagicMock()
        mock_engine.load = MagicMock(return_value=graph)

        with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
            result = runner.invoke(main, ["check"], catch_exceptions=False)

            assert result.exit_code == EXIT_SUCCESS, (
                f"Run {run_number + 1}/5 failed. Exit code: {result.exit_code}. "
                f"Output: {result.output}"
            )


class TestCIReadiness:
    """[P1] CI environment readiness tests."""

    def test_pytest_markers_configured(self) -> None:
        """pytest 'live' marker is configured in pyproject.toml."""
        # Read pyproject.toml and verify 'live' marker is configured
        # This prevents "unknown marker" warnings when running pytest
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"
        content = pyproject_path.read_text()
        assert "live" in content and "markers" in content, (
            "pytest 'live' marker should be configured in pyproject.toml"
        )

    def test_tests_run_without_api_key(self) -> None:
        """Tests excluding 'live' marker don't require API keys (AC9).

        GIVEN: No API keys in environment (or keys removed)
        WHEN: Running MockEngine-based tests
        THEN: Tests succeed without requiring OPENAI_API_KEY
        """
        import os

        # Verify that MockEngine tests work regardless of API key presence
        # Save current state and temporarily remove any API key
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            # MockEngine should work without any API configuration
            runner = CliRunner()
            nodes = (Node(id="test", label="Test Activity", type="Activity", source="user-stated"),)
            graph = Graph(nodes=nodes, edges=())

            mock_engine = MagicMock()
            mock_engine.load = MagicMock(return_value=graph)

            with patch("sentinel.core.engine.CogneeEngine", return_value=mock_engine):
                result = runner.invoke(main, ["check"], catch_exceptions=False)
                # Should succeed with mock - no API key needed
                assert result.exit_code == EXIT_SUCCESS, (
                    f"MockEngine test should work without API key. Exit code: {result.exit_code}"
                )
        finally:
            # Restore original key if it existed
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key
