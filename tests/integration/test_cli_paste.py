"""Integration tests for the paste CLI command with fixtures.

Tests for Story 1.2: Schedule Text Ingestion.
Updated for Story 1.3: Entity Extraction & Graph Building.
Tests full CLI flow using fixture files and MockEngine.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_SUCCESS, EXIT_USER_ERROR
from sentinel.core.types import Edge, Graph, Node

# Fixture directory path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "schedules"


def _create_collision_graph() -> Graph:
    """Create a collision graph matching maya_typical_week scenario."""
    return Graph(
        nodes=(
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
            ),
            Node(
                id="activity-dinner",
                label="Dinner with Aunt Susan",
                type="Activity",
                source="user-stated",
            ),
            Node(
                id="energy-low",
                label="Low Energy",
                type="EnergyState",
                source="ai-inferred",
            ),
            Node(
                id="activity-presentation",
                label="Strategy Presentation",
                type="Activity",
                source="user-stated",
            ),
        ),
        edges=(
            Edge(
                source_id="person-aunt-susan",
                target_id="energy-low",
                relationship="DRAINS",
                confidence=0.81,
            ),
            Edge(
                source_id="activity-dinner",
                target_id="person-aunt-susan",
                relationship="INVOLVES",
                confidence=0.80,
            ),
        ),
    )


def _create_boring_graph() -> Graph:
    """Create a boring graph matching maya_boring_week scenario."""
    return Graph(
        nodes=(
            Node(
                id="activity-standup",
                label="Regular Standup",
                type="Activity",
                source="user-stated",
            ),
            Node(
                id="activity-docs",
                label="Documentation Updates",
                type="Activity",
                source="user-stated",
            ),
        ),
        edges=(
            Edge(
                source_id="activity-standup",
                target_id="timeslot-monday",
                relationship="SCHEDULED_AT",
                confidence=0.90,
            ),
        ),
    )


def _create_unicode_graph() -> Graph:
    """Create a Unicode graph matching maya_edge_cases scenario."""
    return Graph(
        nodes=(
            Node(
                id="person-maria",
                label="María ☕",
                type="Person",
                source="user-stated",
            ),
            Node(
                id="activity-coffee",
                label="Coffee with María ☕",
                type="Activity",
                source="user-stated",
            ),
        ),
        edges=(
            Edge(
                source_id="activity-coffee",
                target_id="person-maria",
                relationship="INVOLVES",
                confidence=0.85,
            ),
        ),
    )


class TestPasteCommandIntegration:
    """Integration tests for the paste command with fixtures."""

    def test_paste_with_maya_typical_week_fixture(self) -> None:
        """Test full CLI flow with maya_typical_week.txt fixture (AC: #1, #2, #3)."""
        fixture_path = FIXTURES_DIR / "maya_typical_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_collision_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
        )
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"
        assert "characters" in result.output.lower(), f"Expected character count: {result.output}"
        # Story 1.3: Should show entity count
        assert "Extracted" in result.output, f"Expected 'Extracted' in output: {result.output}"

    def test_paste_with_maya_boring_week_fixture(self) -> None:
        """Test full CLI flow with maya_boring_week.txt fixture."""
        fixture_path = FIXTURES_DIR / "maya_boring_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_boring_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
        )
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"

    def test_paste_with_maya_edge_cases_fixture_preserves_unicode(self) -> None:
        """Test Unicode handling with maya_edge_cases.txt fixture (AC: #5)."""
        fixture_path = FIXTURES_DIR / "maya_edge_cases.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_unicode_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
        )
        # Verify success message and no encoding errors
        assert "Schedule received" in result.stdout, f"Expected success message: {result.stdout}"

    def test_paste_with_empty_input_shows_error(self) -> None:
        """Test error handling with empty input (AC: #4)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="")

        assert result.exit_code == EXIT_USER_ERROR, (
            f"Expected exit code 1, got {result.exit_code}. Stderr: {result.stderr}"
        )
        assert "No schedule text provided" in result.stderr, (
            f"Expected error message in stderr: {result.stderr}"
        )
        assert "Tip:" in result.stderr, f"Expected helpful tip in stderr: {result.stderr}"

    def test_paste_simulated_pipe_from_file(self) -> None:
        """Test simulated pipe input (AC: #2)."""
        # Simulate: cat schedule.txt | sentinel paste
        fixture_path = FIXTURES_DIR / "maya_typical_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
        # CliRunner's input parameter simulates piped stdin
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_collision_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
        )
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"

    def test_paste_command_exists_in_help(self) -> None:
        """Test that paste command appears in help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"
        assert "paste" in result.output, f"Expected 'paste' in help: {result.output}"

    def test_paste_command_has_help(self) -> None:
        """Test that paste command has its own help."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste", "--help"])

        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"
        assert "schedule" in result.output.lower(), f"Expected schedule in help: {result.output}"

    def test_paste_with_collision_scenario_shows_entities(self) -> None:
        """Test that collision scenario produces expected entity count (Story 1.3)."""
        fixture_path = FIXTURES_DIR / "maya_typical_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        mock_graph = _create_collision_graph()
        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ):
            result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS
        # Should show the number of entities from mock graph
        assert "4 entities" in result.output, f"Expected '4 entities' in output: {result.output}"
        assert "2 relationships" in result.output, (
            f"Expected '2 relationships' in output: {result.output}"
        )
