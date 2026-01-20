"""Unit tests for empty state display functionality.

Tests for Story 2.5: Graceful Empty State.
Tests the display_empty_state function output formatting.
"""

import io

from rich.console import Console

from sentinel.cli.commands import display_empty_state


class TestDisplayEmptyState:
    """Unit tests for display_empty_state function."""

    def test_display_empty_state_shows_header(self) -> None:
        """Empty state shows bold green header with checkmark emoji (AC #1)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(5, target_console=test_console)

        output = captured_output.getvalue()
        assert "NO COLLISIONS DETECTED" in output, (
            f"Expected 'NO COLLISIONS DETECTED' header in output: {output}"
        )

    def test_display_empty_state_shows_checkmark_emoji(self) -> None:
        """Empty state includes checkmark emoji (AC #1)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(5, target_console=test_console)

        output = captured_output.getvalue()
        assert "✅" in output, f"Expected ✅ emoji in output: {output}"

    def test_display_empty_state_shows_relationship_count(self) -> None:
        """Empty state includes count of analyzed relationships (AC #1, #5)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(12, target_console=test_console)

        output = captured_output.getvalue()
        assert "12" in output, f"Expected relationship count '12' in output: {output}"
        assert "analyzed relationships" in output, (
            f"Expected 'analyzed relationships' in output: {output}"
        )

    def test_display_empty_state_shows_zero_relationships(self) -> None:
        """Empty state correctly shows 0 relationships when graph has no edges (AC #5)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(0, target_console=test_console)

        output = captured_output.getvalue()
        # Check for "0" and "analyzed relationships" separately due to Rich ANSI codes
        assert "0" in output, f"Expected '0' in output: {output}"
        assert "analyzed relationships" in output, (
            f"Expected 'analyzed relationships' in output: {output}"
        )

    def test_display_empty_state_includes_motivational_message(self) -> None:
        """Empty state includes 'Go get 'em' motivational message (AC #1)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(5, target_console=test_console)

        output = captured_output.getvalue()
        assert "Go get 'em" in output, f"Expected motivational message in output: {output}"

    def test_display_empty_state_includes_plant_emoji(self) -> None:
        """Empty state includes 🌿 plant emoji (AC #1)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(5, target_console=test_console)

        output = captured_output.getvalue()
        assert "🌿" in output, f"Expected 🌿 emoji in output: {output}"

    def test_display_empty_state_includes_resilient_message(self) -> None:
        """Empty state includes 'energy looks resilient' message (AC #1)."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(5, target_console=test_console)

        output = captured_output.getvalue()
        assert "resilient" in output.lower(), f"Expected 'resilient' in output: {output}"

    def test_display_empty_state_shows_hidden_count(self) -> None:
        """Empty state shows hidden low-confidence count when provided."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(10, hidden_count=3, target_console=test_console)

        output = captured_output.getvalue()
        assert "3" in output, f"Expected hidden count '3' in output: {output}"
        assert "low-confidence" in output.lower(), (
            f"Expected 'low-confidence' mention in output: {output}"
        )
        assert "verbose" in output.lower(), f"Expected '--verbose' hint in output: {output}"

    def test_display_empty_state_no_hidden_message_when_zero(self) -> None:
        """Empty state does not show hidden message when hidden_count is 0."""
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        display_empty_state(10, hidden_count=0, target_console=test_console)

        output = captured_output.getvalue()
        # Should not mention hidden or verbose when no collisions filtered
        assert "hidden" not in output.lower(), (
            f"Should not show hidden message when hidden_count=0: {output}"
        )

    def test_display_empty_state_does_not_raise_exception(self) -> None:
        """Empty state function executes without raising exceptions."""
        # Verify the function doesn't crash with various inputs
        captured_output = io.StringIO()
        test_console = Console(file=captured_output, force_terminal=True)

        # Test with various parameter combinations
        try:
            display_empty_state(5, target_console=test_console)
            display_empty_state(0, target_console=test_console)
            display_empty_state(100, hidden_count=5, target_console=test_console)
        except Exception as e:
            raise AssertionError(f"display_empty_state raised exception: {e}")
