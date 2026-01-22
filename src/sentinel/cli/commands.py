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
    DEFAULT_EXPLORATION_DEPTH,
    EXIT_COLLISION_DETECTED,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
    HIGH_CONFIDENCE,
    LARGE_GRAPH_THRESHOLD,
    MAX_EXPLORATION_DEPTH,
    MEDIUM_CONFIDENCE,
)
from sentinel.core.exceptions import IngestionError, PersistenceError
from sentinel.core.matching import format_node_suggestions, fuzzy_find_node
from sentinel.core.persistence import AcknowledgmentStore, CorrectionStore, get_graph_db_path
from sentinel.core.rules import (
    detect_cross_domain_collisions,
    find_collision_by_label,
    generate_collision_key,
)
from sentinel.core.types import (
    Acknowledgment,
    Correction,
    Graph,
    Node,
    ScoredCollision,
    strip_domain_prefix,
)
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
@click.option(
    "--show-acked",
    "-a",
    is_flag=True,
    help="Show acknowledged collisions with [ACKED] label.",
)
@click.pass_context
def check(ctx: click.Context, verbose: bool, show_acked: bool) -> None:
    """Check your schedule for energy collisions.

    Analyzes the knowledge graph for collision patterns where energy-draining
    activities conflict with activities requiring focus.

    Pattern detected: DRAINS → CONFLICTS_WITH → REQUIRES

    By default, only collisions with confidence >= 50% are shown. Use --verbose
    to see all collisions including low-confidence speculative ones.

    Acknowledged collisions are hidden by default. Use --show-acked to display
    them with an [ACKED] label.

    Examples:
        sentinel check              # Check for collisions in saved graph
        sentinel check --verbose    # Include low-confidence speculative collisions
        sentinel check --show-acked # Show acknowledged collisions with [ACKED] label
        sentinel paste < schedule.txt && sentinel check   # Ingest then check
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from sentinel.core.engine import CogneeEngine
    from sentinel.core.exceptions import PersistenceError
    from sentinel.core.rules import find_collision_paths_async

    debug = ctx.obj.get("debug", False)
    if debug:
        logger.debug("Starting collision check")

    try:
        engine = CogneeEngine()
        # Apply corrections when loading (AC: #5 - deleted nodes filtered)
        graph = engine.load(apply_corrections=True)

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
            confidence_filtered = all_collisions
            low_confidence_hidden = 0
        else:
            confidence_filtered = filter_collisions_by_confidence(all_collisions, MEDIUM_CONFIDENCE)
            low_confidence_hidden = len(all_collisions) - len(confidence_filtered)

        # If all collisions were filtered out by confidence, show success message
        if not confidence_filtered:
            # All collisions below threshold - show empty state with hidden count (AC #1)
            # NOTE: No ASCII graph rendering for empty state (AC #6)
            display_empty_state(len(graph.edges), low_confidence_hidden)
            raise SystemExit(EXIT_SUCCESS)

        # Filter by acknowledgments (Story 3-4)
        ack_store = AcknowledgmentStore()
        acked_keys = ack_store.get_acknowledged_keys()

        unacked_collisions: list[ScoredCollision] = []
        acked_collisions: list[ScoredCollision] = []

        for collision in confidence_filtered:
            key = generate_collision_key(collision)
            if key in acked_keys:
                acked_collisions.append(collision)
            else:
                unacked_collisions.append(collision)

        acked_count = len(acked_collisions)

        # Determine display mode based on --show-acked flag
        if show_acked:
            # Show all collisions including acknowledged with [ACKED] label
            display_collisions = unacked_collisions + acked_collisions
        else:
            display_collisions = unacked_collisions

        # If all collisions are acknowledged and not showing acked, show success
        if not display_collisions and acked_count > 0:
            # All collisions acknowledged - special empty state (AC #6)
            console.print("[green]✓[/green] NO NEW COLLISIONS")
            console.print()
            if acked_count == 1:
                console.print(
                    "[dim](1 acknowledged collision hidden. Use --show-acked to view)[/dim]"
                )
            else:
                console.print(
                    f"[dim]({acked_count} acknowledged collisions hidden. "
                    "Use --show-acked to view)[/dim]"
                )
            raise SystemExit(EXIT_SUCCESS)

        # Display each collision with formatted path and context (Story 2.3)
        console.print()  # Blank line for visual separation
        for i, collision in enumerate(display_collisions, 1):
            # Check if this collision is acknowledged (for [ACKED] label)
            key = generate_collision_key(collision)
            is_acked = key in acked_keys

            if show_acked and is_acked:
                # Display with [ACKED] label and dim styling
                formatted_path = format_collision_path(collision)
                console.print(f"[dim][ACKED] {formatted_path}[/dim]")
            else:
                display_collision_warning(collision, i, graph)
            console.print()  # Blank line between collisions

        # Show summary with filtering info (Story 2.4 AC #5, Story 3-4 AC #5)
        total_collisions = len(unacked_collisions) + acked_count
        if show_acked:
            # Summary for --show-acked mode
            if acked_count > 0:
                console.print(
                    f"[bold]{total_collisions} collisions total[/bold] "
                    f"[dim]({acked_count} acknowledged)[/dim]"
                )
            else:
                plural = "s" if total_collisions != 1 else ""
                console.print(
                    f"[yellow]Found {total_collisions} collision{plural} "
                    "affecting your schedule.[/yellow]"
                )
        else:
            # Default summary (unacknowledged only)
            unacked_count = len(unacked_collisions)
            plural = "s" if unacked_count != 1 else ""
            console.print(
                f"[yellow]Found {unacked_count} collision{plural} affecting your schedule.[/yellow]"
            )
            if acked_count > 0:
                console.print(
                    f"[dim]({total_collisions} collisions detected, "
                    f"{acked_count} acknowledged, hidden)[/dim]"
                )

        if low_confidence_hidden > 0:
            console.print(
                f"[dim]({low_confidence_hidden} low-confidence hidden, use --verbose to show)[/dim]"
            )

        # Show ASCII graph with collision paths highlighted (AC #4)
        collision_paths = [c.path for c in display_collisions]
        console.print()
        console.print("[bold]Knowledge Graph (collision paths highlighted with >>):[/bold]")
        ascii_output = render_ascii(graph, collision_paths=collision_paths)
        console.print(ascii_output, markup=False)

        # Exit code based on unacknowledged collisions
        if unacked_collisions:
            raise SystemExit(EXIT_COLLISION_DETECTED)
        else:
            raise SystemExit(EXIT_SUCCESS)

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


@main.group()
@click.pass_context
def correct(ctx: click.Context) -> None:
    """Manage corrections to AI-inferred nodes.

    Use these commands to delete incorrect AI-inferred nodes from your
    knowledge graph or list existing corrections.

    Example: sentinel correct delete "Drained"
    Example: sentinel correct list
    """
    pass  # Group command doesn't do anything itself


@correct.command(name="delete")
@click.argument("node_label")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def correct_delete(ctx: click.Context, node_label: str, yes: bool) -> None:
    """Delete an AI-inferred node from the knowledge graph.

    NODE_LABEL is the label of the node to delete (supports fuzzy matching).

    Only AI-inferred nodes can be deleted. User-stated nodes from your
    original schedule cannot be modified through this command.

    Examples:
        sentinel correct delete "Drained"           # Exact match
        sentinel correct delete "Drainned" --yes    # Fuzzy match, skip confirmation
    """
    from sentinel.core.engine import CogneeEngine

    try:
        engine = CogneeEngine()
        graph = engine.load()

        if graph is None:
            error_console.print("[yellow]No schedule data found.[/yellow]")
            error_console.print("Run [bold]sentinel paste[/bold] first to add your schedule.")
            raise SystemExit(EXIT_USER_ERROR)

        # Find the node using fuzzy matching (ai-inferred only)
        result = fuzzy_find_node(graph, node_label, ai_inferred_only=True)

        if result.match is None:
            if result.suggestions:
                error_console.print(f"[red]Error:[/red] Node '{node_label}' not found.")
                error_console.print()
                error_console.print(format_node_suggestions(result.suggestions))
            else:
                error_console.print("[red]Error:[/red] No AI-inferred nodes found.")
                error_console.print(
                    "[dim]Only AI-inferred nodes can be deleted. "
                    "User-stated nodes from your schedule cannot be modified.[/dim]"
                )
            raise SystemExit(EXIT_USER_ERROR)

        # If fuzzy match (not exact), ask for confirmation
        if not result.is_exact and not yes:
            console.print(f"[yellow]Did you mean '[bold]{result.match.label}[/bold]'?[/yellow]")
            if not click.confirm("Delete this node?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # For exact match without --yes, still confirm
        if result.is_exact and not yes:
            console.print(f"About to delete node: [bold]{result.match.label}[/bold]")
            console.print(f"[dim]ID: {result.match.id}[/dim]")
            console.print(f"[dim]Type: {result.match.type}[/dim]")
            if not click.confirm("Are you sure?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # Apply the correction
        correction = Correction(node_id=result.match.id, action="delete")

        try:
            mutated_graph = engine.mutate(graph, correction)
        except ValueError as e:
            error_console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(EXIT_USER_ERROR)

        # Persist the correction
        store = CorrectionStore()
        store.add_correction(
            correction,
            reason=f"User deleted via CLI: {result.match.label}",
        )

        # Persist the mutated graph
        engine.persist(mutated_graph)

        console.print(f"[green]✓[/green] Deleted node '[bold]{result.match.label}[/bold]'")

        # Show summary
        removed_edges = len(graph.edges) - len(mutated_graph.edges)
        if removed_edges > 0:
            console.print(f"[dim]Removed {removed_edges} connected edge(s).[/dim]")

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        logger.exception("Failed to load/save graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in correct delete command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


@correct.command(name="modify")
@click.argument("source_label")
@click.option(
    "--target",
    "-t",
    required=True,
    help="Target node label for the edge to modify.",
)
@click.option(
    "--relationship",
    "-r",
    required=True,
    help="New relationship type (e.g., ENERGIZES, DRAINS).",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def correct_modify(
    ctx: click.Context,
    source_label: str,
    target: str,
    relationship: str,
    yes: bool,
) -> None:
    """Modify the relationship type of an edge in the knowledge graph.

    SOURCE_LABEL is the label of the source node (supports fuzzy matching).

    Examples:
        sentinel correct modify "Aunt Susan" --target "drained" --relationship ENERGIZES
        sentinel correct modify "Aunt Susan" -t "drained" -r ENERGIZES --yes
    """
    from sentinel.core.engine import VALID_EDGE_TYPES, CogneeEngine

    try:
        engine = CogneeEngine()
        graph = engine.load()

        if graph is None:
            error_console.print("[yellow]No schedule data found.[/yellow]")
            error_console.print("Run [bold]sentinel paste[/bold] first to add your schedule.")
            raise SystemExit(EXIT_USER_ERROR)

        # Validate relationship type
        valid_types = VALID_EDGE_TYPES | {"ENERGIZES"}
        if relationship not in valid_types:
            error_console.print(f"[red]Error:[/red] Invalid relationship type '{relationship}'.")
            error_console.print(f"[dim]Valid types: {', '.join(sorted(valid_types))}[/dim]")
            raise SystemExit(EXIT_USER_ERROR)

        # Find source node using fuzzy matching (all nodes, not just AI-inferred)
        source_result = fuzzy_find_node(graph, source_label, ai_inferred_only=False)

        if source_result.match is None:
            if source_result.suggestions:
                error_console.print(f"[red]Error:[/red] Source node '{source_label}' not found.")
                error_console.print()
                error_console.print(format_node_suggestions(source_result.suggestions))
            else:
                error_console.print(f"[red]Error:[/red] No nodes found matching '{source_label}'.")
            raise SystemExit(EXIT_USER_ERROR)

        # Find target node using fuzzy matching
        target_result = fuzzy_find_node(graph, target, ai_inferred_only=False)

        if target_result.match is None:
            if target_result.suggestions:
                error_console.print(f"[red]Error:[/red] Target node '{target}' not found.")
                error_console.print()
                error_console.print(format_node_suggestions(target_result.suggestions))
            else:
                error_console.print(f"[red]Error:[/red] No nodes found matching '{target}'.")
            raise SystemExit(EXIT_USER_ERROR)

        source_node = source_result.match
        target_node = target_result.match

        # Find the edge between these nodes
        edge_found = None
        for edge in graph.edges:
            if edge.source_id == source_node.id and edge.target_id == target_node.id:
                edge_found = edge
                break

        if edge_found is None:
            error_console.print(
                f"[red]Error:[/red] No edge found from "
                f"'{source_node.label}' to '{target_node.label}'."
            )
            raise SystemExit(EXIT_USER_ERROR)

        # If fuzzy match (not exact), ask for confirmation
        if (not source_result.is_exact or not target_result.is_exact) and not yes:
            console.print("[yellow]Did you mean this edge?[/yellow]")
            console.print(
                f"  [bold]{source_node.label}[/bold] → {edge_found.relationship} → "
                f"[bold]{target_node.label}[/bold]"
            )
            if not click.confirm("Modify this edge?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # Confirm for exact match without --yes
        if source_result.is_exact and target_result.is_exact and not yes:
            console.print("About to modify edge:")
            console.print(
                f"  [bold]{source_node.label}[/bold] → {edge_found.relationship} → "
                f"[bold]{target_node.label}[/bold]"
            )
            console.print(f"  New relationship: [bold]{relationship}[/bold]")
            if not click.confirm("Are you sure?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # Apply the correction
        correction = Correction(
            node_id=source_node.id,
            action="modify_relationship",
            new_value=relationship,
            target_node_id=target_node.id,
            edge_relationship=edge_found.relationship,
        )

        try:
            mutated_graph = engine.mutate(graph, correction)
        except ValueError as e:
            error_console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(EXIT_USER_ERROR)

        # Persist the correction
        store = CorrectionStore()
        store.add_correction(
            correction,
            reason=f"User modified edge via CLI: {edge_found.relationship} → {relationship}",
        )

        # Persist the mutated graph
        engine.persist(mutated_graph)

        console.print(
            f"[green]✓[/green] Modified edge: "
            f"[bold]{source_node.label}[/bold] → [bold]{relationship}[/bold] → "
            f"[bold]{target_node.label}[/bold]"
        )
        console.print(f"[dim]Changed from {edge_found.relationship}.[/dim]")

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        logger.exception("Failed to load/save graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in correct modify command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


@correct.command(name="remove-edge")
@click.argument("source_label")
@click.option(
    "--target",
    "-t",
    required=True,
    help="Target node label for the edge to remove.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def correct_remove_edge(
    ctx: click.Context,
    source_label: str,
    target: str,
    yes: bool,
) -> None:
    """Remove a specific edge from the knowledge graph.

    Removes the edge between source and target nodes while keeping both nodes.

    SOURCE_LABEL is the label of the source node (supports fuzzy matching).

    Examples:
        sentinel correct remove-edge "Aunt Susan" --target "drained"
        sentinel correct remove-edge "Aunt Susan" -t "drained" --yes
    """
    from sentinel.core.engine import CogneeEngine

    try:
        engine = CogneeEngine()
        graph = engine.load()

        if graph is None:
            error_console.print("[yellow]No schedule data found.[/yellow]")
            error_console.print("Run [bold]sentinel paste[/bold] first to add your schedule.")
            raise SystemExit(EXIT_USER_ERROR)

        # Find source node using fuzzy matching
        source_result = fuzzy_find_node(graph, source_label, ai_inferred_only=False)

        if source_result.match is None:
            if source_result.suggestions:
                error_console.print(f"[red]Error:[/red] Source node '{source_label}' not found.")
                error_console.print()
                error_console.print(format_node_suggestions(source_result.suggestions))
            else:
                error_console.print(f"[red]Error:[/red] No nodes found matching '{source_label}'.")
            raise SystemExit(EXIT_USER_ERROR)

        # Find target node using fuzzy matching
        target_result = fuzzy_find_node(graph, target, ai_inferred_only=False)

        if target_result.match is None:
            if target_result.suggestions:
                error_console.print(f"[red]Error:[/red] Target node '{target}' not found.")
                error_console.print()
                error_console.print(format_node_suggestions(target_result.suggestions))
            else:
                error_console.print(f"[red]Error:[/red] No nodes found matching '{target}'.")
            raise SystemExit(EXIT_USER_ERROR)

        source_node = source_result.match
        target_node = target_result.match

        # Find the edge between these nodes
        edge_found = None
        for edge in graph.edges:
            if edge.source_id == source_node.id and edge.target_id == target_node.id:
                edge_found = edge
                break

        if edge_found is None:
            error_console.print(
                f"[red]Error:[/red] No edge found from "
                f"'{source_node.label}' to '{target_node.label}'."
            )
            raise SystemExit(EXIT_USER_ERROR)

        # If fuzzy match (not exact), ask for confirmation
        if (not source_result.is_exact or not target_result.is_exact) and not yes:
            console.print("[yellow]Did you mean this edge?[/yellow]")
            console.print(
                f"  [bold]{source_node.label}[/bold] → {edge_found.relationship} → "
                f"[bold]{target_node.label}[/bold]"
            )
            if not click.confirm("Remove this edge?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # Confirm for exact match without --yes
        if source_result.is_exact and target_result.is_exact and not yes:
            console.print("About to remove edge:")
            console.print(
                f"  [bold]{source_node.label}[/bold] → {edge_found.relationship} → "
                f"[bold]{target_node.label}[/bold]"
            )
            if not click.confirm("Are you sure?"):
                console.print("[dim]Aborted.[/dim]")
                raise SystemExit(EXIT_SUCCESS)

        # Apply the correction
        correction = Correction(
            node_id=source_node.id,
            action="remove_edge",
            target_node_id=target_node.id,
            edge_relationship=edge_found.relationship,
        )

        try:
            mutated_graph = engine.mutate(graph, correction)
        except ValueError as e:
            error_console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(EXIT_USER_ERROR)

        # Persist the correction
        store = CorrectionStore()
        store.add_correction(
            correction,
            reason=f"User removed edge via CLI: {source_node.label} → {target_node.label}",
        )

        # Persist the mutated graph
        engine.persist(mutated_graph)

        console.print(
            f"[green]✓[/green] Removed edge: "
            f"[bold]{source_node.label}[/bold] → {edge_found.relationship} → "
            f"[bold]{target_node.label}[/bold]"
        )
        console.print("[dim]Both nodes have been preserved.[/dim]")

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        logger.exception("Failed to load/save graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in correct remove-edge command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


@correct.command(name="list")
@click.pass_context
def correct_list(ctx: click.Context) -> None:
    """List all corrections made to the knowledge graph.

    Shows deleted nodes, modified edges, and removed edges.

    Example: sentinel correct list
    """
    try:
        store = CorrectionStore()
        records = store.load_records()

        if not records:
            console.print("[dim]No corrections have been made yet.[/dim]")
            console.print()
            console.print(
                "Use [bold]sentinel correct delete <node>[/bold] "
                "to delete incorrectly inferred nodes."
            )
            console.print(
                "Use [bold]sentinel correct modify[/bold] to change edge relationship types."
            )
            console.print("Use [bold]sentinel correct remove-edge[/bold] to remove specific edges.")
            raise SystemExit(EXIT_SUCCESS)

        console.print(f"[bold]Corrections ({len(records)}):[/bold]")
        console.print()

        for i, record in enumerate(records, 1):
            action = record.get("action", "unknown")
            action_display = action.upper()
            if action == "delete":
                action_display = "[red]DELETE[/red]"
            elif action == "modify_relationship":
                action_display = "[yellow]MODIFY[/yellow]"
            elif action == "remove_edge":
                action_display = "[magenta]REMOVE_EDGE[/magenta]"

            node_id = record.get("node_id", "unknown")
            target_id = record.get("target_node_id", "")
            new_value = record.get("new_value", "")
            old_relationship = record.get("edge_relationship", "")
            timestamp = record.get("timestamp", "")

            # Format timestamp for display (show date only for brevity)
            time_display = ""
            if timestamp:
                # Parse ISO format and show just the date
                time_display = f" [dim]({timestamp[:10]})[/dim]"

            # Format based on action type
            if action == "delete":
                console.print(f"  {i}. {action_display}: {node_id}{time_display}")
            elif action == "modify_relationship":
                # Show old→new relationship format
                if old_relationship:
                    rel_change = f"{old_relationship} → {new_value}"
                else:
                    rel_change = f"→ {new_value}"
                console.print(
                    f"  {i}. {action_display}: {node_id} → {target_id} "
                    f"[dim]({rel_change})[/dim]{time_display}"
                )
            elif action == "remove_edge":
                console.print(f"  {i}. {action_display}: {node_id} → {target_id}{time_display}")
            else:
                console.print(f"  {i}. {action_display}: {node_id}{time_display}")

        raise SystemExit(EXIT_SUCCESS)

    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in correct list command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


@main.command()
@click.argument("label", required=False)
@click.option(
    "--list",
    "-l",
    "list_acks",
    is_flag=True,
    help="List all acknowledged collision warnings.",
)
@click.option(
    "--remove",
    "-r",
    is_flag=True,
    help="Remove an acknowledgment instead of adding one.",
)
@click.pass_context
def ack(
    ctx: click.Context,
    label: str | None,
    list_acks: bool,
    remove: bool,
) -> None:
    """Acknowledge collision warnings to suppress them in future checks.

    LABEL is the collision warning label to acknowledge (supports fuzzy matching).

    Use --list to see all acknowledged collisions.
    Use --remove with LABEL to remove an acknowledgment.

    Examples:
        sentinel ack "aunt-susan"           # Acknowledge collision
        sentinel ack --list                 # List acknowledged
        sentinel ack aunt-susan --remove    # Remove acknowledgment
    """
    from datetime import UTC, datetime

    from sentinel.core.engine import CogneeEngine

    # Handle --list flag
    if list_acks:
        try:
            store = AcknowledgmentStore()
            acks = store.load()

            if not acks:
                console.print("[dim]No acknowledgments yet.[/dim]")
                console.print()
                console.print(
                    "Use [bold]sentinel ack <label>[/bold] to acknowledge a collision warning."
                )
                raise SystemExit(EXIT_SUCCESS)

            console.print(f"[bold]Acknowledged collisions ({len(acks)}):[/bold]")
            console.print()

            for i, a in enumerate(acks, 1):
                timestamp_display = ""
                if a.timestamp:
                    timestamp_display = f" [dim]({a.timestamp[:10]})[/dim]"

                # Show key and path summary
                path_summary = " → ".join(a.path[:3])
                if len(a.path) > 3:
                    path_summary += " → ..."

                console.print(f"  {i}. [bold]{a.collision_key}[/bold]{timestamp_display}")
                console.print(f"     [dim]{path_summary}[/dim]")

            raise SystemExit(EXIT_SUCCESS)

        except SystemExit:
            raise
        except Exception:
            logger.exception("Unhandled exception in ack --list command")
            error_console.print("[red]Unexpected error[/red]")
            raise SystemExit(EXIT_INTERNAL_ERROR)

    # Handle --remove flag
    if remove:
        if not label:
            error_console.print("[red]Error:[/red] Label required with --remove flag.")
            error_console.print("Usage: [bold]sentinel ack <label> --remove[/bold]")
            raise SystemExit(EXIT_USER_ERROR)

        try:
            store = AcknowledgmentStore()
            acks = store.load()

            # Find matching acknowledgment using fuzzy matching
            normalized_label = label.lower().replace(" ", "-")
            match = None
            for ack in acks:
                # Exact key match or exact node_label match
                if ack.collision_key == normalized_label or ack.node_label.lower() == label.lower():
                    match = ack
                    break

            # Fuzzy match if no exact match found
            if match is None and acks:
                from rapidfuzz import fuzz, process

                labels = [a.node_label for a in acks]
                result = process.extractOne(
                    label.lower(),
                    [lbl.lower() for lbl in labels],
                    scorer=fuzz.WRatio,
                )
                if result and result[1] >= 70:  # FUZZY_THRESHOLD
                    matched_idx = [lbl.lower() for lbl in labels].index(result[0])
                    match = acks[matched_idx]

            if match is not None:
                store.remove_acknowledgment(match.collision_key)
                console.print(
                    f"[green]✓[/green] Removed acknowledgment for '{escape(match.node_label)}'"
                )
                raise SystemExit(EXIT_SUCCESS)
            else:
                error_console.print(
                    f"[red]Error:[/red] No acknowledgment found for '{escape(label)}'"
                )
                # Show available acknowledgments
                if acks:
                    keys = [a.collision_key for a in acks]
                    error_console.print(f"[dim]Available: {', '.join(keys)}[/dim]")
                raise SystemExit(EXIT_USER_ERROR)

        except SystemExit:
            raise
        except Exception:
            logger.exception("Unhandled exception in ack --remove command")
            error_console.print("[red]Unexpected error[/red]")
            raise SystemExit(EXIT_INTERNAL_ERROR)

    # Main acknowledgment flow - requires LABEL
    if not label:
        error_console.print("[red]Error:[/red] No label provided.")
        error_console.print("Use [bold]sentinel ack <label>[/bold] to acknowledge a collision.")
        error_console.print("Use [bold]sentinel ack --list[/bold] to see all acknowledgments.")
        raise SystemExit(EXIT_USER_ERROR)

    try:
        engine = CogneeEngine()
        graph = engine.load()

        if graph is None:
            error_console.print("[yellow]No schedule data found.[/yellow]")
            error_console.print("Run [bold]sentinel paste[/bold] first to add your schedule.")
            raise SystemExit(EXIT_USER_ERROR)

        # Detect collisions
        collisions = detect_cross_domain_collisions(graph)

        if not collisions:
            error_console.print("[yellow]No collisions detected.[/yellow]")
            error_console.print(
                "[dim]Run [bold]sentinel check[/bold] to analyze your schedule.[/dim]"
            )
            raise SystemExit(EXIT_USER_ERROR)

        # Find collision by label (fuzzy match)
        collision = find_collision_by_label(label, collisions)

        if collision is None:
            error_console.print(f"[red]Error:[/red] No collision found involving '{escape(label)}'")
            # Show available collisions
            console.print("[dim]Available collisions:[/dim]")
            for c in collisions[:5]:  # Show first 5
                key = generate_collision_key(c)
                console.print(f"  - {key}")
            if len(collisions) > 5:
                console.print(f"  [dim]... and {len(collisions) - 5} more[/dim]")
            raise SystemExit(EXIT_USER_ERROR)

        # Create acknowledgment
        collision_key = generate_collision_key(collision)
        node_label = strip_domain_prefix(collision.path[0]) if collision.path else label
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        acknowledgment = Acknowledgment(
            collision_key=collision_key,
            node_label=node_label,
            path=collision.path,
            timestamp=now,
        )

        # Persist
        store = AcknowledgmentStore()
        store.add_acknowledgment(acknowledgment)

        console.print(f"[green]✓[/green] Acknowledged: {escape(collision_key)} collision")
        console.print("[dim]This warning will be suppressed in future checks.[/dim]")

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        logger.exception("Failed to load graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in ack command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


@main.command(name="graph")
@click.argument("node", required=False)
@click.option(
    "--depth",
    "-d",
    type=int,
    default=DEFAULT_EXPLORATION_DEPTH,
    help=(
        f"Relationship hops to display "
        f"(default: {DEFAULT_EXPLORATION_DEPTH}, max: {MAX_EXPLORATION_DEPTH})."
    ),
)
@click.pass_context
def graph_cmd(ctx: click.Context, node: str | None, depth: int) -> None:
    """Explore the knowledge graph around a specific node.

    If NODE is provided, displays the neighborhood around that node.
    If NODE is omitted, displays the entire graph.

    NODE can be a partial match - fuzzy matching will find close matches.

    Examples:
        sentinel graph                      # Show full graph
        sentinel graph "Aunt Susan"         # Explore around Aunt Susan (depth 2)
        sentinel graph "aunt" --depth 1     # Fuzzy match, immediate neighbors only
        sentinel graph "Aunt Susan" -d 3    # Extended connections (3 hops)
    """
    from sentinel.core.engine import CogneeEngine

    try:
        # Validate depth range (Story 4-2 AC#4, AC#5)
        if depth < 0:
            error_console.print("[red]Error:[/red] Depth must be non-negative.")
            raise SystemExit(EXIT_USER_ERROR)

        if depth > MAX_EXPLORATION_DEPTH:
            console.print(
                f"[yellow]Warning:[/yellow] Maximum depth is {MAX_EXPLORATION_DEPTH}. "
                f"Using --depth {MAX_EXPLORATION_DEPTH}."
            )
            depth = MAX_EXPLORATION_DEPTH

        engine = CogneeEngine()
        graph = engine.load(apply_corrections=True)

        if graph is None or not graph.nodes:
            error_console.print("[red]Error:[/red] No graph found. Run `sentinel paste` first.")
            raise SystemExit(EXIT_USER_ERROR)

        # Full graph display if no node specified
        if node is None:
            output = render_ascii(graph)
            console.print(output, markup=False)
            raise SystemExit(EXIT_SUCCESS)

        # Find the focal node with fuzzy matching (allow ALL nodes)
        match_result = fuzzy_find_node(
            graph,
            node,
            ai_inferred_only=False,  # Allow matching ANY node for graph exploration
        )

        if match_result.match is None:
            # No match found - show error with suggestions
            error_console.print(f"[red]Error:[/red] Node '{escape(node)}' not found in graph.")
            if match_result.suggestions:
                console.print()
                console.print(format_node_suggestions(match_result.suggestions))
            raise SystemExit(EXIT_USER_ERROR)

        focal_node = match_result.match

        # Show fuzzy match notice if not exact
        if not match_result.is_exact:
            console.print(
                f"[dim]Matched: {escape(focal_node.label)} (score: {match_result.score:.0f}%)[/dim]"
            )
            console.print()

        # Extract neighborhood (uses core/graph_ops.py)
        from sentinel.core.graph_ops import extract_neighborhood

        neighborhood = extract_neighborhood(graph, focal_node, depth=depth)

        # Check for large graph warning (Story 4-2 AC#6)
        # Note: We warn but don't truncate - users may want full context.
        # The warning guides them to use lower depth for cleaner output.
        total_nodes = len(neighborhood.nodes)
        if total_nodes > LARGE_GRAPH_THRESHOLD:
            console.print(
                f"[yellow]Warning:[/yellow] Large graph ({total_nodes} nodes). "
                "Use lower --depth for cleaner output."
            )

        # Render with focal node highlighted
        output = render_ascii(neighborhood, focal_node_label=focal_node.label)
        console.print(output, markup=False)

        # Summary
        console.print()
        console.print(
            f"[dim]Showing {len(neighborhood.nodes)} nodes, "
            f"{len(neighborhood.edges)} relationships "
            f"(depth {depth} from {escape(focal_node.label)})[/dim]"
        )

        raise SystemExit(EXIT_SUCCESS)

    except PersistenceError as e:
        logger.exception("Failed to load graph")
        error_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(EXIT_INTERNAL_ERROR)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled exception in graph command")
        error_console.print("[red]Unexpected error[/red]")
        raise SystemExit(EXIT_INTERNAL_ERROR)


if __name__ == "__main__":
    main()
