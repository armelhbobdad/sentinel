"""Verbose logging utilities for CLI commands.

Story 5.5: Help Text & Verbose Mode - AC4, AC5
Provides user-friendly operation logging with timestamps and durations.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import click
from rich.console import Console

# Verbose output always goes to stderr to avoid polluting stdout
_verbose_console = Console(stderr=True, highlight=False)


class VerboseLogger:
    """Logger for verbose operation output to stderr.

    Provides timestamped logging with operation timing support.
    All output goes to stderr to avoid polluting stdout (AC5).
    """

    def __init__(self, enabled: bool = False) -> None:
        """Initialize verbose logger.

        Args:
            enabled: Whether verbose output is enabled.
        """
        self.enabled = enabled
        self._start_times: dict[str, float] = {}
        self._console = _verbose_console

    def log(self, message: str) -> None:
        """Log a verbose message with timestamp.

        Args:
            message: Message to log.
        """
        if not self.enabled:
            return
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        self._console.print(f"[dim][{timestamp}][/dim] {message}")

    def start_operation(self, name: str) -> None:
        """Start timing an operation.

        Args:
            name: Operation name for tracking.
        """
        self._start_times[name] = time.perf_counter()
        self.log(f"Starting: {name}")

    def end_operation(self, name: str, result: str | None = None) -> None:
        """End timing an operation and log duration.

        Args:
            name: Operation name.
            result: Optional result summary.
        """
        if name in self._start_times:
            duration = time.perf_counter() - self._start_times[name]
            duration_str = f"({duration:.2f}s)"
            del self._start_times[name]
        else:
            duration_str = ""

        if result:
            self.log(f"Completed: {name} {duration_str} - {result}")
        else:
            self.log(f"Completed: {name} {duration_str}")

    @contextmanager
    def operation(self, name: str) -> Iterator["VerboseLogger"]:
        """Context manager for timing an operation.

        Args:
            name: Operation name.

        Yields:
            Self for chained calls.
        """
        self.start_operation(name)
        try:
            yield self
        finally:
            pass  # Don't auto-end - caller should end_operation with result


def get_verbose_logger(ctx: click.Context) -> VerboseLogger:
    """Get verbose logger from Click context.

    Args:
        ctx: Click context with obj dict.

    Returns:
        VerboseLogger instance based on verbose flag.
    """
    if ctx.obj is None:
        return VerboseLogger(enabled=False)
    verbose = ctx.obj.get("verbose", False)
    return VerboseLogger(enabled=verbose)
