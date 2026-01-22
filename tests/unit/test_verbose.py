"""Tests for verbose logging utilities.

Tests for Story 5.5: Help Text & Verbose Mode.
"""

import re
import time
from io import StringIO
from unittest.mock import patch

import pytest

from sentinel.cli.verbose import VerboseLogger, get_verbose_logger


class TestVerboseLoggerDisabled:
    """Tests for VerboseLogger when disabled."""

    def test_verbose_logger_disabled_produces_no_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """VerboseLogger(enabled=False) produces no output."""
        vlog = VerboseLogger(enabled=False)
        vlog.log("test message")
        captured = capsys.readouterr()
        assert captured.err == "", f"Expected no stderr output, got: {captured.err}"
        assert captured.out == "", f"Expected no stdout output, got: {captured.out}"

    def test_verbose_logger_disabled_start_operation_no_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """start_operation() produces no output when disabled."""
        vlog = VerboseLogger(enabled=False)
        vlog.start_operation("test_op")
        captured = capsys.readouterr()
        assert captured.err == "", f"Expected no stderr output, got: {captured.err}"

    def test_verbose_logger_disabled_end_operation_no_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """end_operation() produces no output when disabled."""
        vlog = VerboseLogger(enabled=False)
        vlog.start_operation("test_op")
        vlog.end_operation("test_op", "result")
        captured = capsys.readouterr()
        assert captured.err == "", f"Expected no stderr output, got: {captured.err}"


class TestVerboseLoggerEnabled:
    """Tests for VerboseLogger when enabled."""

    def test_verbose_logger_enabled_outputs_to_stderr(self) -> None:
        """VerboseLogger with enabled=True outputs to stderr."""
        # Rich Console with stderr=True writes to stderr
        # We need to capture Rich's output by patching the console
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.file = output
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.log("test message")

        assert "test message" in output.getvalue(), (
            f"Expected 'test message' in output, got: {output.getvalue()}"
        )

    def test_verbose_logger_includes_timestamp(self) -> None:
        """Each verbose message includes HH:MM:SS timestamp."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.log("test message")

        # Timestamp format: [HH:MM:SS]
        timestamp_pattern = r"\[\d{2}:\d{2}:\d{2}\]"
        assert re.search(timestamp_pattern, output.getvalue()), (
            f"Expected timestamp in format [HH:MM:SS], got: {output.getvalue()}"
        )

    def test_verbose_logger_start_operation_logs_message(self) -> None:
        """start_operation() logs 'Starting: {name}'."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.start_operation("Build graph")

        assert "Starting: Build graph" in output.getvalue(), (
            f"Expected 'Starting: Build graph' in output, got: {output.getvalue()}"
        )

    def test_verbose_logger_end_operation_logs_duration(self) -> None:
        """end_operation() logs duration in seconds."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.start_operation("test_op")
            time.sleep(0.1)  # Sleep 100ms
            vlog.end_operation("test_op")

        # Should contain duration in format (X.XXs)
        duration_pattern = r"\(\d+\.\d+s\)"
        assert re.search(duration_pattern, output.getvalue()), (
            f"Expected duration in format (X.XXs), got: {output.getvalue()}"
        )
        assert "Completed: test_op" in output.getvalue(), (
            f"Expected 'Completed: test_op' in output, got: {output.getvalue()}"
        )

    def test_verbose_logger_end_operation_with_result(self) -> None:
        """end_operation() includes result string when provided."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.start_operation("Load graph")
            vlog.end_operation("Load graph", "15 nodes")

        assert "15 nodes" in output.getvalue(), (
            f"Expected '15 nodes' in output, got: {output.getvalue()}"
        )
        assert "Completed: Load graph" in output.getvalue(), (
            f"Expected 'Completed: Load graph' in output, got: {output.getvalue()}"
        )

    def test_verbose_logger_end_operation_without_start(self) -> None:
        """end_operation() works even if start_operation wasn't called."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            vlog.end_operation("unknown_op", "result")

        # Should log completion without duration
        assert "Completed: unknown_op" in output.getvalue(), (
            f"Expected 'Completed: unknown_op' in output, got: {output.getvalue()}"
        )
        assert "result" in output.getvalue(), (
            f"Expected 'result' in output, got: {output.getvalue()}"
        )

    def test_verbose_logger_operation_context_manager(self) -> None:
        """operation() context manager tracks timing."""
        output = StringIO()
        vlog = VerboseLogger(enabled=True)

        with patch.object(vlog, "_console") as mock_console:
            mock_console.print = lambda msg, **kwargs: output.write(str(msg) + "\n")
            with vlog.operation("Process data"):
                time.sleep(0.05)
                vlog.end_operation("Process data", "done")

        assert "Starting: Process data" in output.getvalue(), (
            f"Expected 'Starting: Process data' in output, got: {output.getvalue()}"
        )
        assert "Completed: Process data" in output.getvalue(), (
            f"Expected 'Completed: Process data' in output, got: {output.getvalue()}"
        )


class TestGetVerboseLogger:
    """Tests for get_verbose_logger helper function."""

    def test_get_verbose_logger_returns_disabled_when_flag_false(self) -> None:
        """get_verbose_logger returns disabled logger when verbose=False."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.obj = {"verbose": False}

        vlog = get_verbose_logger(ctx)

        assert isinstance(vlog, VerboseLogger), "Expected VerboseLogger instance"
        assert vlog.enabled is False, "Expected logger to be disabled"

    def test_get_verbose_logger_returns_enabled_when_flag_true(self) -> None:
        """get_verbose_logger returns enabled logger when verbose=True."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.obj = {"verbose": True}

        vlog = get_verbose_logger(ctx)

        assert isinstance(vlog, VerboseLogger), "Expected VerboseLogger instance"
        assert vlog.enabled is True, "Expected logger to be enabled"

    def test_get_verbose_logger_returns_disabled_when_key_missing(self) -> None:
        """get_verbose_logger returns disabled logger when verbose key is missing."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.obj = {}  # No verbose key

        vlog = get_verbose_logger(ctx)

        assert isinstance(vlog, VerboseLogger), "Expected VerboseLogger instance"
        assert vlog.enabled is False, "Expected logger to be disabled when key missing"

    def test_get_verbose_logger_returns_disabled_when_obj_none(self) -> None:
        """get_verbose_logger handles None obj gracefully."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.obj = None

        # Should not raise, should return disabled logger
        vlog = get_verbose_logger(ctx)

        assert isinstance(vlog, VerboseLogger), "Expected VerboseLogger instance"
        assert vlog.enabled is False, "Expected logger to be disabled when obj is None"
