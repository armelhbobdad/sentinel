"""CLI commands for Sentinel."""

import asyncio
import io
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import click
from rich.console import Console
from rich.status import Status

from sentinel import __version__
from sentinel.core.constants import EXIT_INTERNAL_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR
from sentinel.core.exceptions import IngestionError, PersistenceError
from sentinel.core.persistence import get_graph_db_path
from sentinel.viz import render_ascii

logger = logging.getLogger(__name__)
console = Console()
error_console = Console(stderr=True)


@contextmanager
def _suppress_cognee_output(debug: bool) -> Iterator[None]:
    """Suppress Cognee's verbose structlog output unless in debug mode.

    Cognee uses structlog which outputs directly to stderr, bypassing
    Python's standard logging configuration. This context manager
    redirects stderr to suppress the noise for better UX.
    """
    if debug:
        # Debug mode: let all output through
        yield
        return

    # Suppress stderr (where structlog outputs)
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    # Also suppress stdout for Cognee's print statements
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        yield
    finally:
        # Restore original streams
        sys.stderr = old_stderr
        sys.stdout = old_stdout


def _configure_logging(debug: bool) -> None:
    """Configure logging levels based on debug flag."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("cognee").setLevel(logging.ERROR)
        logging.getLogger("structlog").setLevel(logging.ERROR)


@click.group()
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging output")
@click.version_option(version=__version__, prog_name="sentinel")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """Sentinel - Personal Energy Guardian CLI.

    Detect schedule conflicts that calendars miss. Sentinel uses knowledge graphs
    to find hidden energy collisions in your schedule.

    Example: sentinel --help
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    _configure_logging(debug)


@main.command()
@click.pass_context
def paste(ctx: click.Context) -> None:
    """Paste your schedule text for analysis.

    Read schedule text from stdin (interactive or piped).

    Examples:
        sentinel paste              # Interactive: type text, then Ctrl+D
        cat schedule.txt | sentinel paste   # Piped from file
        sentinel paste < schedule.txt       # Redirected from file
    """
    debug = ctx.obj.get("debug", False)

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
        # Suppress Cognee's verbose logs unless --debug is passed
        # Import CogneeEngine lazily inside suppression context to catch import-time logs
        with Status("[bold blue]Building knowledge graph...[/bold blue]", console=console):
            with _suppress_cognee_output(debug):
                from sentinel.core.engine import CogneeEngine

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

        # Render ASCII visualization (Story 1.5)
        console.print()  # Blank line separator
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        status_msg = (
            f"[bold blue]Visualizing {node_count} entities "
            f"and {edge_count} relationships...[/bold blue]"
        )
        with Status(status_msg, console=console):
            ascii_output = render_ascii(graph)

        console.print("[bold]Knowledge Graph:[/bold]")
        # Use markup=False to prevent Rich from interpreting [label] as style tags
        # Our node labels use [label] for user-stated nodes
        console.print(ascii_output, markup=False)

        # Add legend explaining node styling
        console.print()
        console.print("[dim]Legend: [name] = user-stated, (name) = AI-inferred[/dim]")

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
