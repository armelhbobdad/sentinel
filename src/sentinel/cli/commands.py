"""CLI commands for Sentinel."""

import logging
import sys

import click
from rich.console import Console

from sentinel import __version__
from sentinel.core.constants import EXIT_INTERNAL_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR

logger = logging.getLogger(__name__)
console = Console()
error_console = Console(stderr=True)


@click.group()
@click.version_option(version=__version__, prog_name="sentinel")
def main() -> None:
    """Sentinel - Personal Energy Guardian CLI.

    Detect schedule conflicts that calendars miss. Sentinel uses knowledge graphs
    to find hidden energy collisions in your schedule.

    Example: sentinel --help
    """
    pass


@main.command()
def paste() -> None:
    """Paste your schedule text for analysis.

    Read schedule text from stdin (interactive or piped).

    Examples:
        sentinel paste              # Interactive: type text, then Ctrl+D
        cat schedule.txt | sentinel paste   # Piped from file
        sentinel paste < schedule.txt       # Redirected from file
    """
    try:
        # Read all input from stdin (works for interactive and piped)
        text = sys.stdin.read()

        # Validate input is not empty
        if not text.strip():
            error_console.print("[red]Error:[/red] No schedule text provided")
            error_console.print(
                "[dim]Tip: Paste your schedule and press Ctrl+D (EOF) to submit.[/dim]"
            )
            raise SystemExit(EXIT_USER_ERROR)

        # Confirm receipt and show character count
        console.print("[green]Schedule received. Processing...[/green]")
        console.print(f"[dim]Received {len(text)} characters.[/dim]")

        # TODO: Story 1.3 will add entity extraction here

        raise SystemExit(EXIT_SUCCESS)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in paste command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


if __name__ == "__main__":
    main()
