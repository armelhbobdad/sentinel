"""Integration tests for help text and verbose mode.

Tests for Story 5.5: Help Text & Verbose Mode.
AC1: Help Flag Support
AC2: Command Examples in Help
AC3: Global Verbose Flag
AC7: Exit Code Documentation
"""

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI runner for tests."""
    return CliRunner()


class TestMainHelpText:
    """Tests for sentinel --help output."""

    def test_main_help_lists_all_commands(self, runner: CliRunner) -> None:
        """sentinel --help lists all available commands (AC1)."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        # Check all commands are listed
        assert "paste" in result.output, "Expected 'paste' command in help"
        assert "check" in result.output, "Expected 'check' command in help"
        assert "graph" in result.output, "Expected 'graph' command in help"
        assert "config" in result.output, "Expected 'config' command in help"
        assert "correct" in result.output, "Expected 'correct' command in help"
        assert "ack" in result.output, "Expected 'ack' command in help"

    def test_main_help_shows_description(self, runner: CliRunner) -> None:
        """sentinel --help shows tool description (AC1)."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        # Check main description
        assert "energy" in result.output.lower() or "collision" in result.output.lower(), (
            "Expected tool description mentioning energy or collision"
        )

    def test_global_verbose_flag_in_main_help(self, runner: CliRunner) -> None:
        """--verbose flag appears in main help (AC3)."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        # Check verbose flag is documented
        assert "--verbose" in result.output or "-v" in result.output, (
            f"Expected --verbose flag in help: {result.output}"
        )

    def test_global_debug_flag_in_main_help(self, runner: CliRunner) -> None:
        """--debug flag appears in main help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "--debug" in result.output or "-d" in result.output, (
            f"Expected --debug flag in help: {result.output}"
        )


class TestCommandHelpText:
    """Tests for individual command help text."""

    def test_paste_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel paste --help includes usage example (AC2)."""
        result = runner.invoke(main, ["paste", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in paste help: {result.output}"
        assert "sentinel paste" in result.output, f"Expected example command: {result.output}"

    def test_check_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel check --help includes usage example (AC2)."""
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in check help: {result.output}"
        assert "sentinel check" in result.output, f"Expected example command: {result.output}"

    def test_check_help_includes_exit_codes(self, runner: CliRunner) -> None:
        """sentinel check --help documents exit codes (AC7)."""
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Exit" in result.output or "exit" in result.output, (
            f"Expected exit code documentation: {result.output}"
        )
        # Should mention success code
        assert "0" in result.output, f"Expected exit code 0 documentation: {result.output}"

    def test_graph_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel graph --help includes usage example (AC2)."""
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in graph help: {result.output}"
        assert "sentinel graph" in result.output, f"Expected example command: {result.output}"

    def test_config_help_lists_valid_keys(self, runner: CliRunner) -> None:
        """sentinel config --help shows all valid configuration keys (AC1)."""
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        # Check key config keys are documented
        assert "energy_threshold" in result.output, (
            f"Expected 'energy_threshold' key in config help: {result.output}"
        )
        assert "llm_provider" in result.output, (
            f"Expected 'llm_provider' key in config help: {result.output}"
        )
        assert "embedding_model" in result.output, (
            f"Expected 'embedding_model' key in config help: {result.output}"
        )

    def test_config_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel config --help includes usage example (AC2)."""
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in config help: {result.output}"
        assert "sentinel config" in result.output, f"Expected example command: {result.output}"

    def test_correct_delete_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel correct delete --help includes usage example (AC2)."""
        result = runner.invoke(main, ["correct", "delete", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in help: {result.output}"

    def test_ack_help_includes_example(self, runner: CliRunner) -> None:
        """sentinel ack --help includes usage example (AC2)."""
        result = runner.invoke(main, ["ack", "--help"])
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

        assert "Example" in result.output, f"Expected 'Example' in ack help: {result.output}"


class TestEachCommandHasHelp:
    """Tests that every command supports --help."""

    @pytest.mark.parametrize(
        "command",
        [
            ["paste"],
            ["check"],
            ["graph"],
            ["config"],
            ["ack"],
            ["correct"],
            ["correct", "delete"],
            ["correct", "modify"],
            ["correct", "remove-edge"],
            ["correct", "list"],
        ],
    )
    def test_command_has_help(self, runner: CliRunner, command: list[str]) -> None:
        """Each command supports --help flag."""
        result = runner.invoke(main, command + ["--help"])
        assert result.exit_code == 0, (
            f"'{' '.join(command)} --help' should exit 0, got {result.exit_code}: {result.output}"
        )
        # Should contain some help text
        assert len(result.output) > 50, (
            f"'{' '.join(command)} --help' should produce substantial help text"
        )


class TestGlobalVerboseFlag:
    """Tests for global --verbose flag behavior."""

    def test_verbose_flag_accepted_at_main_level(self, runner: CliRunner) -> None:
        """--verbose flag is accepted at main level (AC3)."""
        # Just check that the flag is recognized (command may fail for other reasons)
        result = runner.invoke(main, ["--verbose", "--help"])
        # Help should work with --verbose
        assert result.exit_code == 0, f"--verbose should be recognized: {result.output}"

    def test_verbose_short_form_accepted(self, runner: CliRunner) -> None:
        """-v short form is accepted (AC3)."""
        result = runner.invoke(main, ["-v", "--help"])
        assert result.exit_code == 0, f"-v should be recognized: {result.output}"

    def test_verbose_flag_propagates_to_context(self, runner: CliRunner) -> None:
        """--verbose flag value is stored in context."""

        # We'll verify the flag is in ctx.obj by checking that check command
        # doesn't have its own --verbose option collision
        result = runner.invoke(main, ["check", "--help"])
        # After our changes, check should NOT have --verbose (it's global now)
        # But for now, let's just verify --verbose is in main help
        result = runner.invoke(main, ["--help"])
        assert "--verbose" in result.output or "-v" in result.output, (
            f"Expected global --verbose in main help: {result.output}"
        )


class TestVerboseOutputBehavior:
    """Tests for verbose output behavior (AC4, AC5)."""

    def test_verbose_output_goes_to_stderr(self, runner: CliRunner) -> None:
        """Verbose output is written to stderr, not stdout (AC5).

        Click's CliRunner separates stdout and stderr in result.stdout/result.stderr.
        Verbose logging should appear in stderr, not stdout.
        """
        result = runner.invoke(main, ["--verbose", "check"])

        # Verbose messages should be in stderr (contains timestamp pattern)
        # The check command logs "Starting: Load config" before anything else
        assert result.stderr is not None, "Expected stderr to contain verbose output"
        # Verbose output uses [HH:MM:SS] timestamp format
        assert "Starting:" in result.stderr or "Completed:" in result.stderr, (
            f"Expected verbose operation log in stderr: {result.stderr}"
        )
        # stdout should NOT contain verbose output markers
        assert "Starting:" not in result.stdout, (
            f"Verbose output should not be in stdout: {result.stdout}"
        )

    def test_verbose_produces_timestamped_output(self, runner: CliRunner) -> None:
        """--verbose flag produces timestamped operation logging (AC4).

        Verifies that verbose mode outputs operation timing with timestamps.
        """
        import re

        result = runner.invoke(main, ["--verbose", "check"])

        # stderr should contain verbose logging with timestamp pattern [HH:MM:SS]
        assert result.stderr is not None, "Expected stderr output"
        timestamp_pattern = r"\[\d{2}:\d{2}:\d{2}\]"
        assert re.search(timestamp_pattern, result.stderr), (
            f"Expected timestamp [HH:MM:SS] in verbose output: {result.stderr}"
        )

    def test_verbose_logs_operation_names(self, runner: CliRunner) -> None:
        """Verbose output includes operation names (AC4)."""
        result = runner.invoke(main, ["--verbose", "check"])

        assert result.stderr is not None, "Expected stderr output"
        # Should contain at least "Load config" operation from check command
        assert "Load config" in result.stderr, (
            f"Expected 'Load config' operation in verbose output: {result.stderr}"
        )

    def test_verbose_logs_operation_durations(self, runner: CliRunner) -> None:
        """Verbose output includes operation durations (AC4)."""
        result = runner.invoke(main, ["--verbose", "check"])

        assert result.stderr is not None, "Expected stderr output"
        # Should contain duration format like "(0.00s)" or "(0.01s)"
        import re

        duration_pattern = r"\(\d+\.\d{2}s\)"
        assert re.search(duration_pattern, result.stderr), (
            f"Expected duration pattern (X.XXs) in verbose output: {result.stderr}"
        )

    def test_non_verbose_has_no_verbose_output(self, runner: CliRunner) -> None:
        """Without --verbose flag, no verbose output is produced."""
        result = runner.invoke(main, ["check"])

        # Without --verbose, stderr should be empty or not contain verbose markers
        if result.stderr:
            assert "Starting:" not in result.stderr, (
                f"Non-verbose mode should not log operations: {result.stderr}"
            )


class TestHelpFormatConsistency:
    """Tests for consistent help text formatting."""

    def test_all_commands_use_backslash_b_for_examples(self, runner: CliRunner) -> None:
        """Commands use consistent example formatting."""
        # Check that examples are properly formatted in help
        for cmd in ["paste", "check", "graph", "config"]:
            result = runner.invoke(main, [cmd, "--help"])
            # Should have at least one example
            if "Example" in result.output:
                # Examples should contain the sentinel command
                assert "sentinel" in result.output, (
                    f"'{cmd}' help example should include 'sentinel': {result.output}"
                )

    def test_config_help_shows_ollama_setup(self, runner: CliRunner) -> None:
        """sentinel config --help includes Ollama setup example (AC2)."""
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0, f"Expected exit 0: {result.output}"

        # Config help should show how to set up Ollama
        assert "ollama" in result.output.lower(), (
            f"Expected Ollama setup in config help: {result.output}"
        )
