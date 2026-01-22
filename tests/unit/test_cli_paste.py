"""Unit tests for the paste CLI command.

Tests for Story 1.2: Schedule Text Ingestion.
Updated for Story 1.3: Entity Extraction & Graph Building.
"""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_INTERNAL_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR
from sentinel.core.types import Edge, Graph, Node


def _create_mock_graph() -> Graph:
    """Create a mock graph for testing CLI output."""
    return Graph(
        nodes=(
            Node(id="person-steve", label="Steve", type="Person", source="user-stated"),
            Node(
                id="activity-meeting",
                label="Meeting",
                type="Activity",
                source="user-stated",
            ),
        ),
        edges=(
            Edge(
                source_id="activity-meeting",
                target_id="person-steve",
                relationship="INVOLVES",
                confidence=0.85,
            ),
        ),
    )


class TestPasteCommand:
    """Tests for the paste command."""

    def test_paste_with_valid_input_returns_success(self) -> None:
        """Test that valid input returns exit code 0 (AC: #1, #3)."""
        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
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
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=unicode_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # Should not raise errors with Unicode
        assert "Schedule received" in result.stdout, f"Expected success message: {result.stdout}"

    def test_paste_preserves_emoji(self) -> None:
        """Test that emoji are preserved (AC: #5)."""
        runner = CliRunner()
        emoji_text = "Tuesday: Team meeting 🎉\n"
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=emoji_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_preserves_cjk_characters(self) -> None:
        """Test that CJK characters are preserved (AC: #5)."""
        runner = CliRunner()
        cjk_text = "Wednesday: 日本語テスト\n"
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=cjk_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_preserves_accented_characters(self) -> None:
        """Test that accented characters are preserved (AC: #5)."""
        runner = CliRunner()
        accented_text = "Meeting with Jean-Pierre about the über-important project\n"
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=accented_text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"

    def test_paste_shows_character_count(self) -> None:
        """Test that confirmation shows character count (AC: #3)."""
        runner = CliRunner()
        text = "Monday: Meeting\n"
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input=text)

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        assert "characters" in result.output.lower(), (
            f"Expected character count in output: {result.output}"
        )

    def test_paste_with_piped_input_works(self) -> None:
        """Test that piped input works via CliRunner (AC: #2)."""
        runner = CliRunner()
        # CliRunner's input parameter simulates piped stdin
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
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
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
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
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=_create_mock_graph(),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # AC #1 specifies: "Schedule received. Processing..."
        assert "Schedule received. Processing..." in result.output, (
            f"Expected exact message 'Schedule received. Processing...' in output: {result.output}"
        )

    def test_paste_shows_entity_count(self) -> None:
        """Test that completion shows entity count (Story 1.3 AC: #4)."""
        runner = CliRunner()
        mock_graph = _create_mock_graph()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting with Steve\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # Should show entity count
        assert "Extracted" in result.output, f"Expected 'Extracted' in output: {result.output}"
        assert "entities" in result.output, f"Expected 'entities' in output: {result.output}"

    def test_paste_shows_relationship_count(self) -> None:
        """Test that completion shows relationship count (Story 1.3 AC: #4)."""
        runner = CliRunner()
        mock_graph = _create_mock_graph()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting with Steve\n")

        assert result.exit_code == EXIT_SUCCESS, f"Expected exit code 0, got {result.exit_code}"
        # Should show relationship count
        assert "relationships" in result.output, (
            f"Expected 'relationships' in output: {result.output}"
        )

    def test_paste_handles_ingestion_error(self) -> None:
        """Test that IngestionError returns exit code 2 (Story 1.3 AC: #6)."""
        from sentinel.core.exceptions import IngestionError

        runner = CliRunner()
        with patch(
            "sentinel.core.engine.CogneeEngine.ingest",
            new_callable=AsyncMock,
            side_effect=IngestionError("Failed to process schedule: API timeout"),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting with Steve\n")

        assert result.exit_code == EXIT_INTERNAL_ERROR, (
            f"Expected exit code 2, got {result.exit_code}"
        )
        assert "Failed to process schedule" in result.stderr, (
            f"Expected error message in stderr: {result.stderr}"
        )


class TestPasteFormatOption:
    """Tests for the paste command --format option (Story 4.4)."""

    def test_paste_default_format_is_text(self) -> None:
        """Default format is text - no HTML file created (AC: #3)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            # Check that no HTML file was created
            from pathlib import Path

            assert not Path("sentinel-paste.html").exists(), (
                "HTML file should not be created for default format"
            )

    def test_paste_format_html_creates_file(self) -> None:
        """sentinel paste --format html creates HTML file (AC: #2, #4)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(
                    main, ["paste", "--format", "html"], input="Monday: Meeting\n"
                )

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            from pathlib import Path

            assert Path("sentinel-paste.html").exists(), "HTML file should be created"
            assert "Graph saved to" in result.output, f"Expected success message: {result.output}"

    def test_paste_format_html_output_option(self) -> None:
        """--output option specifies custom filename (AC: #4)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(
                    main,
                    ["paste", "--format", "html", "--output", "my-schedule.html"],
                    input="Monday: Meeting\n",
                )

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            from pathlib import Path

            assert Path("my-schedule.html").exists(), "Custom HTML file should be created"

    def test_paste_format_short_form(self) -> None:
        """-f short form works same as --format (AC: #6)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(main, ["paste", "-f", "html"], input="Monday: Meeting\n")

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            from pathlib import Path

            assert Path("sentinel-paste.html").exists(), "HTML file should be created with -f"

    def test_paste_format_invalid_shows_error(self) -> None:
        """Invalid format shows Click error (AC: #5)."""
        runner = CliRunner()
        result = runner.invoke(main, ["paste", "--format", "pdf"], input="Monday: Meeting\n")

        assert result.exit_code == 2, f"Expected exit code 2, got {result.exit_code}"
        # Click shows: "Invalid value for '--format': 'pdf' is not one of 'text', 'html'."
        assert "Invalid value" in result.output or "invalid" in result.output.lower(), (
            f"Expected error about invalid format: {result.output}"
        )

    def test_paste_html_is_self_contained(self) -> None:
        """HTML output has no external URLs (AC: code review learning)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                runner.invoke(main, ["paste", "-f", "html"], input="Monday: Meeting\n")

            from pathlib import Path

            html_content = Path("sentinel-paste.html").read_text()
            assert "http://" not in html_content, "HTML should not contain http:// URLs"
            assert "https://" not in html_content, "HTML should not contain https:// URLs"

    def test_paste_output_short_form(self) -> None:
        """-o short form works same as --output (AC: #6)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(
                    main,
                    ["paste", "-f", "html", "-o", "custom.html"],
                    input="Monday: Meeting\n",
                )

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            from pathlib import Path

            assert Path("custom.html").exists(), "Custom HTML file should be created with -o"

    def test_paste_format_text_shows_ascii(self) -> None:
        """--format text shows ASCII visualization (AC: #1)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=_create_mock_graph(),
            ):
                result = runner.invoke(
                    main, ["paste", "--format", "text"], input="Monday: Meeting\n"
                )

            assert result.exit_code == EXIT_SUCCESS, f"Got: {result.output}"
            # ASCII visualization shows "Knowledge Graph:" header
            assert "Knowledge Graph:" in result.output, (
                f"Expected ASCII visualization: {result.output}"
            )
            # And the legend
            assert "Legend:" in result.output, f"Expected legend: {result.output}"

    def test_paste_empty_input_with_format_html(self) -> None:
        """Empty input with --format html shows error before HTML generation (edge case)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["paste", "--format", "html"], input="")

            assert result.exit_code == EXIT_USER_ERROR, (
                f"Expected exit code 1, got {result.exit_code}"
            )
            assert "No schedule text provided" in result.stderr, (
                f"Expected error message in stderr: {result.stderr}"
            )
            # Verify no HTML file was created
            from pathlib import Path

            assert not Path("sentinel-paste.html").exists(), (
                "HTML file should not be created for empty input"
            )

    def test_paste_html_write_permission_denied(self) -> None:
        """Permission denied when writing HTML returns internal error (edge case)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with (
                patch(
                    "sentinel.core.engine.CogneeEngine.ingest",
                    new_callable=AsyncMock,
                    return_value=_create_mock_graph(),
                ),
                patch(
                    "sentinel.cli.commands._write_html_file",
                    return_value=False,  # Simulate write failure
                ),
            ):
                result = runner.invoke(
                    main, ["paste", "--format", "html"], input="Monday: Meeting\n"
                )

            assert result.exit_code == EXIT_INTERNAL_ERROR, (
                f"Expected exit code 2, got {result.exit_code}"
            )


class TestFormatOptionConsistency:
    """Tests for --format option consistency across commands (Story 4.4 AC: #3, #4, #6)."""

    def test_all_viz_commands_have_format_option(self) -> None:
        """All visualization commands support --format option (AC: #4)."""
        runner = CliRunner()

        # Test that --format is recognized by each command (shows in help)
        for cmd in ["check", "graph", "paste"]:
            result = runner.invoke(main, [cmd, "--help"])
            assert "--format" in result.output, (
                f"'{cmd}' command should have --format option: {result.output}"
            )
            assert "-f" in result.output, (
                f"'{cmd}' command should have -f short form: {result.output}"
            )

    def test_all_viz_commands_have_output_option(self) -> None:
        """All visualization commands support --output option (AC: #4)."""
        runner = CliRunner()

        for cmd in ["check", "graph", "paste"]:
            result = runner.invoke(main, [cmd, "--help"])
            assert "--output" in result.output, (
                f"'{cmd}' command should have --output option: {result.output}"
            )
            assert "-o" in result.output, (
                f"'{cmd}' command should have -o short form: {result.output}"
            )

    def test_all_viz_commands_default_to_text(self) -> None:
        """All visualization commands default to text format (AC: #3)."""
        runner = CliRunner()

        for cmd in ["check", "graph", "paste"]:
            result = runner.invoke(main, [cmd, "--help"])
            # Check that the help text mentions "text" as default or the choice
            assert "text" in result.output, (
                f"'{cmd}' help should mention 'text' format: {result.output}"
            )
            assert "html" in result.output, (
                f"'{cmd}' help should mention 'html' format: {result.output}"
            )

    def test_all_viz_commands_reject_invalid_format(self) -> None:
        """All visualization commands reject invalid format values (AC: #5)."""
        runner = CliRunner()

        for cmd in ["check", "graph", "paste"]:
            # Provide minimal input to avoid stdin blocking
            input_text = "test\n" if cmd == "paste" else None
            result = runner.invoke(main, [cmd, "--format", "pdf"], input=input_text)
            assert result.exit_code == 2, (
                f"'{cmd}' should reject invalid format with exit code 2: {result.exit_code}"
            )
            assert "Invalid value" in result.output or "invalid" in result.output.lower(), (
                f"'{cmd}' should show invalid format error: {result.output}"
            )
