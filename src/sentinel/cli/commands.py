"""CLI commands for Sentinel."""

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.status import Status

from sentinel import __version__
from sentinel.core.constants import EXIT_INTERNAL_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR
from sentinel.core.engine import CogneeEngine
from sentinel.core.exceptions import IngestionError, PersistenceError
from sentinel.core.persistence import get_graph_db_path

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

        # Build knowledge graph with progress indicator (AC #4)
        with Status("[bold blue]Building knowledge graph...[/bold blue]", console=console):
            engine = CogneeEngine()
            graph = asyncio.run(engine.ingest(text))

        # Show completion summary
        console.print(f"[green]✓[/green] Extracted {len(graph.nodes)} entities")
        console.print(f"[dim]Found {len(graph.edges)} relationships.[/dim]")

        # Persist the graph (Story 1.4)
        with Status("[bold blue]Saving knowledge graph...[/bold blue]", console=console):
            engine.persist(graph)

        db_path = get_graph_db_path()
        console.print(f"[green]✓[/green] Graph saved to {db_path}")

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        # Handle persistence failures (Story 1.4)
        logger.exception("Persistence failed")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except IngestionError as e:
        # Handle Cognee API failures (AC #6)
        logger.exception("Ingestion failed")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in paste command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


if __name__ == "__main__":
    main()
