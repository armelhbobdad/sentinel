"""Fuzzy node matching utilities for Sentinel.

Provides fuzzy matching for node lookup with suggestions when
exact matches aren't found. Uses RapidFuzz for fuzzy string matching.
"""

from dataclasses import dataclass, field
from typing import Literal

from sentinel.core.types import Graph, Node

# Default threshold for fuzzy matching (70% as per story requirements)
FUZZY_THRESHOLD = 70

# Number of suggestions to show when no match found
MAX_SUGGESTIONS = 5


@dataclass
class MatchResult:
    """Result of a fuzzy node match operation.

    Attributes:
        match: The matched node, or None if no match found.
        is_exact: True if the match was exact (not fuzzy).
        score: The fuzzy match score (0-100), or 100 for exact match.
        suggestions: List of suggested node labels when no match found.
        candidates: List of candidate nodes for ambiguous matches.
    """

    match: Node | None = None
    is_exact: bool = False
    score: float = 0.0
    suggestions: list[str] = field(default_factory=list)
    candidates: list[Node] = field(default_factory=list)


def fuzzy_find_node(
    graph: Graph,
    query: str,
    match_by: Literal["label", "id"] = "label",
    ai_inferred_only: bool = True,
    threshold: int = FUZZY_THRESHOLD,
) -> MatchResult:
    """Find a node by fuzzy matching on label or ID.

    Searches for nodes with exact match first (case-insensitive),
    then falls back to fuzzy matching above the threshold.
    Only matches AI-inferred nodes by default (user-stated nodes
    cannot be deleted).

    Args:
        graph: The graph to search in.
        query: The search query (node label or ID).
        match_by: Field to match against ("label" or "id").
        ai_inferred_only: If True, only match ai-inferred nodes.
        threshold: Minimum fuzzy match score (0-100).

    Returns:
        MatchResult with matched node, suggestions, and candidates.
    """
    # Filter to eligible nodes
    eligible_nodes = list(graph.nodes)
    if ai_inferred_only:
        eligible_nodes = [n for n in eligible_nodes if n.source == "ai-inferred"]

    if not eligible_nodes:
        return MatchResult(match=None, suggestions=[], candidates=[])

    # Get the field to match against
    def get_field(node: Node) -> str:
        if match_by == "id":
            return node.id
        return node.label

    query_lower = query.lower()

    # Try exact match first (case-insensitive)
    for node in eligible_nodes:
        if get_field(node).lower() == query_lower:
            return MatchResult(match=node, is_exact=True, score=100.0)

    # Try fuzzy matching using RapidFuzz
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        # Graceful degradation: no fuzzy matching without RapidFuzz
        suggestions = [get_field(n) for n in eligible_nodes[:MAX_SUGGESTIONS]]
        return MatchResult(match=None, suggestions=suggestions, candidates=eligible_nodes)

    # Build choices list
    choices = {get_field(n): n for n in eligible_nodes}

    # Use extract to get all matches above threshold
    matches = process.extract(
        query,
        choices.keys(),
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
        limit=MAX_SUGGESTIONS,
    )

    if not matches:
        # No matches above threshold - return suggestions
        all_matches = process.extract(
            query,
            choices.keys(),
            scorer=fuzz.WRatio,
            limit=MAX_SUGGESTIONS,
        )
        suggestions = [m[0] for m in all_matches]
        return MatchResult(match=None, suggestions=suggestions, candidates=[])

    # Check for ambiguous matches (multiple high-scoring candidates)
    top_score = matches[0][1]
    candidates = [choices[m[0]] for m in matches if m[1] >= top_score - 10]

    if len(candidates) > 1:
        # Ambiguous - return candidates for user confirmation
        suggestions = [get_field(n) for n in candidates]
        return MatchResult(
            match=None,
            suggestions=suggestions,
            candidates=candidates,
            score=top_score,
        )

    # Single match above threshold
    best_match = matches[0]
    matched_node = choices[best_match[0]]
    return MatchResult(
        match=matched_node,
        is_exact=False,
        score=best_match[1],
        candidates=[matched_node],
    )


def get_ai_inferred_nodes(graph: Graph) -> list[Node]:
    """Get all AI-inferred nodes from a graph.

    Args:
        graph: The graph to search.

    Returns:
        List of nodes with source="ai-inferred".
    """
    return [n for n in graph.nodes if n.source == "ai-inferred"]


def format_node_suggestions(suggestions: list[str], max_show: int = 5) -> str:
    """Format node suggestions for display in error messages.

    Args:
        suggestions: List of suggested node labels.
        max_show: Maximum number of suggestions to show.

    Returns:
        Formatted string with suggestions.
    """
    if not suggestions:
        return "No AI-inferred nodes available."

    shown = suggestions[:max_show]
    formatted = "\n".join(f"  - {s}" for s in shown)

    if len(suggestions) > max_show:
        formatted += f"\n  ... and {len(suggestions) - max_show} more"

    return f"Did you mean one of these?\n{formatted}"
