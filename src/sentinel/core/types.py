"""Core data types for Sentinel.

These types define the graph schema and collision detection structures.
All types are immutable dataclasses for thread safety and predictability.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal

# Source types for tracking provenance
NodeSource = Literal["user-stated", "ai-inferred"]


class Domain(Enum):
    """Life domains for collision classification.

    Used to identify when energy collisions cross life boundaries
    (e.g., social activities impacting professional requirements).
    """

    SOCIAL = auto()  # Family, friends, social events
    PROFESSIONAL = auto()  # Work, meetings, career activities
    HEALTH = auto()  # Exercise, medical, wellness
    PERSONAL = auto()  # Default/ambiguous


@dataclass(frozen=True)
class Node:
    """A node in the knowledge graph.

    Attributes:
        id: Unique identifier for the node.
        label: Human-readable label for the node.
        type: The entity type (Person, Activity, EnergyState, TimeSlot).
        source: How this node was created - user-stated or ai-inferred.
        metadata: Additional data associated with the node.
    """

    id: str
    label: str
    type: str
    source: NodeSource
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    """An edge connecting two nodes in the knowledge graph.

    Attributes:
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship: The relationship type (DRAINS, REQUIRES, CONFLICTS_WITH, etc.).
        confidence: Confidence score for this edge (0.0 to 1.0).
        metadata: Additional data associated with the edge.
    """

    source_id: str
    target_id: str
    relationship: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Graph:
    """A knowledge graph containing nodes and edges.

    Attributes:
        nodes: Immutable sequence of nodes in the graph.
        edges: Immutable sequence of edges connecting nodes.
    """

    nodes: tuple[Node, ...] = field(default_factory=tuple)
    edges: tuple[Edge, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScoredCollision:
    """A detected collision with confidence scoring.

    Represents a path through the graph that indicates an energy collision,
    along with confidence scores and source breakdown.

    Attributes:
        path: The collision path as a tuple of node/edge labels (immutable).
        confidence: Overall confidence score for this collision (0.0 to 1.0).
        source_breakdown: Breakdown of source counts (ai_inferred, user_stated).
    """

    path: tuple[str, ...]
    confidence: float
    source_breakdown: Mapping[str, int] = field(default_factory=dict)


def strip_domain_prefix(label: str) -> str:
    """Strip domain prefix from a path label.

    Domain prefixes like "[SOCIAL] Aunt Susan" or "[PROFESSIONAL]Meeting"
    are added by collision detection to show domain transitions.
    This function removes them to get the bare entity label.

    Args:
        label: A path element that may contain a domain prefix.

    Returns:
        The label without the domain prefix, with leading whitespace stripped.
        Returns the original label if no domain prefix is found.

    Examples:
        >>> strip_domain_prefix("[SOCIAL] Aunt Susan")
        'Aunt Susan'
        >>> strip_domain_prefix("[PROFESSIONAL]Meeting")
        'Meeting'
        >>> strip_domain_prefix("Regular Label")
        'Regular Label'
    """
    if label.startswith("["):
        bracket_end = label.find("]")
        if bracket_end != -1:
            # Handle both "[DOMAIN] name" and "[DOMAIN]name" formats
            return label[bracket_end + 1 :].lstrip()
    return label


@dataclass(frozen=True)
class Correction:
    """A user correction to the graph.

    Used to modify or delete AI-inferred nodes/edges based on user feedback.

    Attributes:
        node_id: ID of the node to correct.
        action: The correction action (delete, modify).
        new_value: New value for modify action, None for delete.
    """

    node_id: str
    action: str
    new_value: str | None = None
