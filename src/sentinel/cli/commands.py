"""CLI commands for Sentinel."""

import asyncio
import io
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import click
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.status import Status

from sentinel import __version__
from sentinel.core.constants import (
    EXIT_COLLISION_DETECTED,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
)
from sentinel.core.exceptions import IngestionError, PersistenceError
from sentinel.core.persistence import get_graph_db_path
from sentinel.core.types import Graph, Node, ScoredCollision, strip_domain_prefix
from sentinel.viz import render_ascii

logger = logging.getLogger(__name__)
console = Console()
error_console = Console(stderr=True)


def filter_collisions_by_confidence(
    collisions: list[ScoredCollision], min_threshold: float
) -> list[ScoredCollision]:
    """Filter collisions to only include those at or above the confidence threshold.

    Args:
        collisions: List of scored collisions to filter.
        min_threshold: Minimum confidence threshold (inclusive).

    Returns:
        List of collisions with confidence >= min_threshold.
    """
    return [c for c in collisions if c.confidence >= min_threshold]


def sort_collisions_by_confidence(
    collisions: list[ScoredCollision],
) -> list[ScoredCollision]:
    """Sort collisions by confidence in descending order (highest first).

    Uses stable sort to preserve order for equal confidence values.

    Args:
        collisions: List of scored collisions to sort.

    Returns:
        New list sorted by confidence descending.
    """
    return sorted(collisions, key=lambda c: c.confidence, reverse=True)


def format_collision_path(collision: ScoredCollision) -> str:
    """Format collision path for display with Rich markup.

    Args:
        collision: The scored collision with path tuple.

    Returns:
        Rich-formatted string with arrows between elements.
        Entities (even indices) are bold, relationships (odd indices) are dim.
    """
    parts = []
    for i, element in enumerate(collision.path):
        # Escape Rich markup in element (handles [SOCIAL], [Meeting], etc.)
        safe_element = escape(element)

        if i % 2 == 0:  # Entity (bold)
            parts.append(f"[bold]{safe_element}[/bold]")
        else:  # Relationship (dim)
            parts.append(f"[dim]{safe_element}[/dim]")

    return " → ".join(parts)


def get_confidence_level(confidence: float) -> str:
    """Classify confidence score into HIGH, MEDIUM, or LOW.

    Args:
        confidence: Confidence score between 0.0 and 1.0.

    Returns:
        "HIGH" if >= 0.8, "MEDIUM" if >= 0.5, "LOW" otherwise.
    """
    if confidence >= HIGH_CONFIDENCE:
        return "HIGH"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "MEDIUM"
    else:
        return "LOW"


def extract_temporal_context(collision: ScoredCollision, graph: Graph) -> str | None:
    """Extract temporal relationship for collision explanation.

    Looks up nodes in the collision path and extracts day/time metadata
    to generate a human-readable temporal context message.

    Args:
        collision: The scored collision to analyze.
        graph: The graph containing full node information.

    Returns:
        Human-readable temporal context or None if no temporal data.
    """
    # Build node lookup from labels
    nodes_by_label: dict[str, Node] = {}
    for node in graph.nodes:
        nodes_by_label[node.label] = node

    # Get source and target labels (first and last entities in path)
    # Handle domain prefixes like "[SOCIAL] Aunt Susan"
    source_label_raw = collision.path[0]
    target_label_raw = collision.path[-1]

    # Strip domain prefix if present (e.g., "[SOCIAL] Aunt Susan" -> "Aunt Susan")
    source_label = strip_domain_prefix(source_label_raw)
    target_label = strip_domain_prefix(target_label_raw)

    # Look up nodes
    source_node = nodes_by_label.get(source_label)
    target_node = nodes_by_label.get(target_label)

    # Extract temporal data
    source_day = None
    target_day = None

    if source_node:
        source_day = source_node.metadata.get("day")
    if target_node:
        target_day = target_node.metadata.get("day")

    # Generate context message if we have temporal data
    if source_day and target_day:
        return (
            f"Your {source_day} activity may drain energy needed for {target_day}'s requirements."
        )
    elif source_day:
        return f"This activity on {source_day} may impact your energy levels."
    elif target_day:
        return f"The affected activity is scheduled for {target_day}."

    return None


def display_empty_state(
    relationships_analyzed: int,
    hidden_count: int = 0,
    target_console: Console | None = None,
) -> None:
    """Display a positive empty state message when no collisions are found.

    Args:
        relationships_analyzed: Number of relationships that were checked.
        hidden_count: Number of low-confidence collisions hidden (for summary).
        target_console: Optional Rich console (defaults to module console).
    """
    output_console = target_console if target_console is not None else console

    # Header with checkmark emoji (bold green)
    output_console.print("[bold green]✅  NO COLLISIONS DETECTED[/bold green]")
    output_console.print()

    # Supportive message
    output_console.print("Your energy looks resilient this week.")
    output_console.print(
        f"No invisible conflicts found across {relationships_analyzed} analyzed relationships."
    )
    output_console.print("Go get 'em. 🌿")

    # Show hidden count if applicable
    if hidden_count > 0:
        output_console.print()
        output_console.print(
            f"[dim]({hidden_count} low-confidence speculative results hidden, "
            "use --verbose to show)[/dim]"
        )


def display_collision_warning(
    collision: ScoredCollision,
    index: int,
    graph: Graph,
    target_console: Console | None = None,
) -> None:
    """Display a collision warning panel with path and context.

    Args:
        collision: The scored collision to display.
        index: Collision number (1-based) for the header.
        graph: Graph for temporal context extraction.
        target_console: Optional Rich console (defaults to module console).
    """
    output_console = target_console if target_console is not None else console

    # Determine severity based on confidence
    confidence_level = get_confidence_level(collision.confidence)
    confidence_pct = int(collision.confidence * 100)

    if confidence_level == "HIGH":
        header = f"⚠️  COLLISION DETECTED                    Confidence: {confidence_pct}%"
        border_style = "red bold"
    elif confidence_level == "MEDIUM":
        header = f"⚡ POTENTIAL RISK                         Confidence: {confidence_pct}%"
        border_style = "yellow"
    else:  # LOW - only shown when verbose=True
        header = f"💭 SPECULATIVE                            Confidence: {confidence_pct}%"
        border_style = "dim"

    # Format the collision path
    formatted_path = format_collision_path(collision)

    # Extract temporal context
    temporal = extract_temporal_context(collision, graph)

    # Build panel content
    content_parts = [formatted_path]
    if temporal:
        content_parts.append("")
        content_parts.append(f"📅 {temporal}")

    content = "\n".join(content_parts)

    # Create and display panel
    panel = Panel(
        content,
        title=f"[bold]COLLISION #{index}[/bold]",
        subtitle=header,
        border_style=border_style,
    )
    output_console.print(panel)


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


@main.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show all collisions including low-confidence speculative ones.",
)
@click.pass_context
def check(ctx: click.Context, verbose: bool) -> None:
    """Check your schedule for energy collisions.

    Analyzes the knowledge graph for collision patterns where energy-draining
    activities conflict with activities requiring focus.

    Pattern detected: DRAINS → CONFLICTS_WITH → REQUIRES

    By default, only collisions with confidence >= 50% are shown. Use --verbose
    to see all collisions including low-confidence speculative ones.

    Examples:
        sentinel check              # Check for collisions in saved graph
        sentinel check --verbose    # Include low-confidence speculative collisions
        sentinel paste < schedule.txt && sentinel check   # Ingest then check
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from sentinel.core.engine import CogneeEngine
    from sentinel.core.exceptions import PersistenceError
    from sentinel.core.rules import (
        detect_cross_domain_collisions,
        find_collision_paths_async,
    )

    debug = ctx.obj.get("debug", False)
    if debug:
        logger.debug("Starting collision check")

    try:
        engine = CogneeEngine()
        graph = engine.load()

        if graph is None:
            error_console.print("[yellow]No schedule data found.[/yellow]")
            error_console.print("Run [bold]sentinel paste[/bold] first to add your schedule.")
            raise SystemExit(EXIT_USER_ERROR)

        if not graph.edges:
            # No relationships to analyze - show empty state with 0 count (AC #5)
            # NOTE: No ASCII graph rendering for empty state (AC #6)
            display_empty_state(0)
            raise SystemExit(EXIT_SUCCESS)

        # Track progress during traversal
        relationships_analyzed = [0]  # Mutable container for closure

        def update_progress(count: int) -> None:
            relationships_analyzed[0] = count

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(
                f"Analyzing {len(graph.edges)} relationships...",
                total=None,
            )

            # Run async traversal with timeout support
            result = asyncio.run(
                find_collision_paths_async(
                    graph,
                    progress_callback=update_progress,
                )
            )

            # Update description with actual count
            progress.update(
                task,
                description=f"Analyzed {result.relationships_analyzed} relationships...",
            )

        # Handle timeout warning
        if result.timed_out:
            error_console.print("[yellow]Analysis timed out. Showing partial results.[/yellow]")

        # Use domain-enhanced collision detection (Story 2.2/2.3)
        all_collisions = detect_cross_domain_collisions(graph)

        if not all_collisions:
            # No collisions detected - show positive empty state (AC #1)
            # NOTE: No ASCII graph rendering for empty state (AC #6)
            display_empty_state(len(graph.edges))
            raise SystemExit(EXIT_SUCCESS)

        # Sort collisions by confidence descending (Story 2.4 AC #7)
        all_collisions = sort_collisions_by_confidence(all_collisions)

        # Filter by confidence unless verbose (Story 2.4 AC #5)
        if verbose:
            display_collisions = all_collisions
            hidden_count = 0
        else:
            display_collisions = filter_collisions_by_confidence(all_collisions, MEDIUM_CONFIDENCE)
            hidden_count = len(all_collisions) - len(display_collisions)

        # If all collisions were filtered out, show success message
        if not display_collisions:
            # All collisions below threshold - show empty state with hidden count (AC #1)
            # NOTE: No ASCII graph rendering for empty state (AC #6)
            display_empty_state(len(graph.edges), hidden_count)
            raise SystemExit(EXIT_SUCCESS)

        # Display each collision with formatted path and context (Story 2.3)
        console.print()  # Blank line for visual separation
        for i, collision in enumerate(display_collisions, 1):
            display_collision_warning(collision, i, graph)
            console.print()  # Blank line between collisions

        # Show summary with filtering info (Story 2.4 AC #5)
        collision_count = len(display_collisions)
        plural = "s" if collision_count != 1 else ""
        summary = (
            f"[yellow]Found {collision_count} collision{plural} affecting your schedule.[/yellow]"
        )
        console.print(summary)

        if hidden_count > 0:
            console.print(
                f"[dim]({hidden_count} low-confidence hidden, use --verbose to show)[/dim]"
            )

        # Show ASCII graph with collision paths highlighted (AC #4)
        collision_paths = [c.path for c in display_collisions]
        console.print()
        console.print("[bold]Knowledge Graph (collision paths highlighted with >>):[/bold]")
        ascii_output = render_ascii(graph, collision_paths=collision_paths)
        console.print(ascii_output, markup=False)

        raise SystemExit(EXIT_COLLISION_DETECTED)

    except PersistenceError as e:
        logger.exception("Failed to load graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in check command")
        error_console.print("[red]Unexpected error during check[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


if __name__ == "__main__":
    main()
