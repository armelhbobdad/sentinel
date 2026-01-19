"""Integration tests for the paste CLI command with fixtures.

Tests for Story 1.2: Schedule Text Ingestion.
Tests full CLI flow using fixture files.
"""

from pathlib import Path

from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_SUCCESS, EXIT_USER_ERROR

# Fixture directory path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "schedules"


class TestPasteCommandIntegration:
    """Integration tests for the paste command with fixtures."""

    def test_paste_with_maya_typical_week_fixture(self) -> None:
        """Test full CLI flow with maya_typical_week.txt fixture (AC: #1, #2, #3)."""
        fixture_path = FIXTURES_DIR / "maya_typical_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input=fixture_text)

        assert result.exit_code == EXIT_SUCCESS, (
            f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
        )
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"
        assert "characters" in result.output.lower(), f"Expected character count: {result.output}"

    def test_paste_with_maya_boring_week_fixture(self) -> None:
        """Test full CLI flow with maya_boring_week.txt fixture."""
        fixture_path = FIXTURES_DIR / "maya_boring_week.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")

        runner = CliRunner()
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
