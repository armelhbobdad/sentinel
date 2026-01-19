"""Unit tests for the paste CLI command.

Tests for Story 1.2: Schedule Text Ingestion.
"""

from unittest.mock import patch

from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_INTERNAL_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR


class TestPasteCommand:
    """Tests for the paste command."""

    def test_paste_with_valid_input_returns_success(self) -> None:
        """Test that valid input returns exit code 0 (AC: #1, #3)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="Monday: Meeting with Steve\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        assert "Schedule received" in result.output, (
            f"Expected 'Schedule received' in output: {result.output}"
        )

    def test_paste_with_empty_input_returns_error(self) -> None:
        """Test that empty input returns exit code 1 (AC: #4)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="")

        assert result.exit_code == EXIT_USER_ERROR, f"Expected exit code 1, got {result.exit_code}"
        assert "No schedule text provided" in result.stderr, (
            f"Expected error message in stderr: {result.stderr}"
        )

    def test_paste_with_whitespace_only_returns_error(self) -> None:
        """Test that whitespace-only input returns exit code 1 (AC: #4)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="   \n\t\n   ")

        assert result.exit_code == EXIT_USER_ERROR, f"Expected exit code 1, got {result.exit_code}"
        assert "No schedule text provided" in result.stderr, (
            f"Expected error message in stderr: {result.stderr}"
        )

    def test_paste_shows_helpful_tip_on_empty_input(self) -> None:
        """Test that empty input shows helpful tip (AC: #4)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="")

        assert "Tip:" in result.stderr, f"Expected tip in stderr: {result.stderr}"
        assert "Ctrl+D" in result.stderr or "EOF" in result.stderr, (
            f"Expected EOF hint: {result.stderr}"
        )

    def test_paste_preserves_unicode_characters(self) -> None:
        """Test that Unicode characters are preserved (AC: #5)."""
        runner = CliRunner()
        unicode_text = "Monday: Coffee with María ☕\n"
        result = runner.invoke(main, ["paste"], input=unicode_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # Should not raise errors with Unicode
        assert "Schedule received" in result.stdout, f"Expected success message: {result.stdout}"

    def test_paste_preserves_emoji(self) -> None:
        """Test that emoji are preserved (AC: #5)."""
        runner = CliRunner()
        emoji_text = "Tuesday: Team meeting 🎉\n"
        result = runner.invoke(main, ["paste"], input=emoji_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_preserves_cjk_characters(self) -> None:
        """Test that CJK characters are preserved (AC: #5)."""
        runner = CliRunner()
        cjk_text = "Wednesday: 日本語テスト\n"
        result = runner.invoke(main, ["paste"], input=cjk_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_preserves_accented_characters(self) -> None:
        """Test that accented characters are preserved (AC: #5)."""
        runner = CliRunner()
        accented_text = "Meeting with Jean-Pierre about the über-important project\n"
        result = runner.invoke(main, ["paste"], input=accented_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_shows_character_count(self) -> None:
        """Test that confirmation shows character count (AC: #3)."""
        runner = CliRunner()
        text = "Monday: Meeting\n"
        result = runner.invoke(main, ["paste"], input=text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        assert "characters" in result.output.lower(), (
            f"Expected character count in output: {result.output}"
        )

    def test_paste_with_piped_input_works(self) -> None:
        """Test that piped input works via CliRunner (AC: #2)."""
        runner = CliRunner()
        # CliRunner's input parameter simulates piped stdin
        result = runner.invoke(main, ["paste"], input="Piped schedule text\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"

    def test_paste_with_multiline_input(self) -> None:
        """Test that multiline input is accepted (AC: #1, #3)."""
        runner = CliRunner()
        multiline = """Monday: Team standup
Tuesday: 1:1 with manager
Wednesday: Project review
Thursday: Sprint planning
Friday: Demo"""
        result = runner.invoke(main, ["paste"], input=multiline)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        assert "Schedule received" in result.output, f"Expected confirmation: {result.output}"

    def test_paste_with_unexpected_exception_returns_internal_error(self) -> None:
        """Test that unexpected exceptions return exit code 2 with generic message."""
        runner = CliRunner()

        # Mock console.print to raise an unexpected exception during success path
        # (CliRunner intercepts stdin, so we can't mock sys.stdin.read effectively)
        with patch(
            "sentinel.cli.commands.console.print",
            side_effect=RuntimeError("Simulated error"),
        ):
            result = runner.invoke(main, ["paste"], input="Valid input\n")

        assert result.exit_code == EXIT_INTERNAL_ERROR, (
            f"Expected exit code 2, got {result.exit_code}"
        )
        # Error should go to stderr and be generic (not expose exception details)
        assert "Unexpected error" in result.stderr, (
            f"Expected generic error in stderr: {result.stderr}"
        )

    def test_paste_shows_exact_success_message(self) -> None:
        """Test that success message matches AC #1 exactly."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # AC #1 specifies: "Schedule received. Processing..."
        assert "Schedule received. Processing..." in result.output, (
            f"Expected exact message 'Schedule received. Processing...' in output: {result.output}"
        )
