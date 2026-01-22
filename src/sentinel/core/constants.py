"""Constants for Sentinel application.

Exit codes, traversal limits, and confidence thresholds.
"""

from typing import Final

# Exit codes (following Unix conventions)
EXIT_SUCCESS: Final[int] = 0
EXIT_USER_ERROR: Final[int] = 1
EXIT_INTERNAL_ERROR: Final[int] = 2
EXIT_CONFIG_ERROR: Final[int] = 3
# FR29: Exit code 1 when collision detected (intentionally same as user error)
EXIT_COLLISION_DETECTED: Final[int] = 1

# Graph traversal constants (Story 2.1)
MAX_DEPTH: Final[int] = 3  # Maximum hops for collision detection (FR10)
DEFAULT_TIMEOUT: Final[int] = 5  # Seconds per traversal hop (NFR6)
MAX_CHECK_TIME: Final[int] = 15  # Total check command timeout (NFR1)

# Confidence thresholds for collision scoring
# HIGH_CONFIDENCE (0.8): Collision shown as "COLLISION DETECTED" (red bold)
# MEDIUM_CONFIDENCE (0.5): Collision shown as "POTENTIAL RISK" (yellow)
#                          This is also the default filtering threshold
# Collisions below MEDIUM_CONFIDENCE shown as "SPECULATIVE" (dim) with --verbose
HIGH_CONFIDENCE: Final[float] = 0.8
MEDIUM_CONFIDENCE: Final[float] = 0.5

# Energy threshold confidence mappings (Story 5.2)
# These map energy_threshold config values to confidence filter thresholds
# Used by get_confidence_threshold() to convert config string to filter value
ENERGY_THRESHOLD_LOW: Final[float] = 0.3
ENERGY_THRESHOLD_MEDIUM: Final[float] = 0.5  # Same as MEDIUM_CONFIDENCE
ENERGY_THRESHOLD_HIGH: Final[float] = 0.7

ENERGY_THRESHOLD_MAP: Final[dict[str, float]] = {
    "low": ENERGY_THRESHOLD_LOW,
    "medium": ENERGY_THRESHOLD_MEDIUM,
    "high": ENERGY_THRESHOLD_HIGH,
}

# AI-inferred node confidence penalty factor
# Each AI-inferred node in a collision path reduces confidence by 10%
AI_INFERRED_PENALTY: Final[float] = 0.9

# Domain classification keywords (Story 2.2)
# Keywords used to classify nodes into life domains for cross-domain collision detection

SOCIAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "family",
        "dinner",
        "aunt",
        "uncle",
        "cousin",
        "friend",
        "party",
        "birthday",
        "wedding",
        "holiday",
        "reunion",
        "brunch",
        "coffee with",
        "visit",
        "call mom",
        "call dad",
        "mom",
        "dad",
        "sister",
        "brother",
        "grandmother",
        "grandfather",
        "niece",
        "nephew",
    }
)

PROFESSIONAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "meeting",
        "presentation",
        "sync",
        "standup",
        "review",
        "deadline",
        "project",
        "client",
        "boss",
        "colleague",
        "sprint",
        "demo",
        "interview",
        "conference",
        "workshop",
        # Note: "work" removed - too broad, matches "homework", "network", etc.
        # Use more specific keywords like "work meeting", "office" instead
        "office",
        "strategy",
        "quarterly",
        "report",
        "workday",  # More specific than "work"
        "workplace",  # More specific than "work"
    }
)

HEALTH_KEYWORDS: frozenset[str] = frozenset(
    {
        "workout",
        "gym",
        "yoga",
        "run",
        "exercise",
        "hiit",
        "doctor",
        "dentist",
        "therapy",
        "meditation",
        "sleep",
        "fitness",
        "training",
        "cardio",
        "stretch",
    }
)

# Cross-domain confidence boost factor
# Cross-domain collisions get a 10% confidence boost as they're more impactful
CROSS_DOMAIN_BOOST: Final[float] = 1.1

# Relationship types for collision pattern (Story 2.2 code review fix)
# Used in pattern matching to avoid magic strings
REL_DRAINS: Final[str] = "DRAINS"
REL_CONFLICTS_WITH: Final[str] = "CONFLICTS_WITH"
REL_REQUIRES: Final[str] = "REQUIRES"

# Node types for collision validation (Story 2.2 code review fix)
NODE_TYPE_PERSON: Final[str] = "Person"
NODE_TYPE_ACTIVITY: Final[str] = "Activity"
NODE_TYPE_ENERGY_STATE: Final[str] = "EnergyState"
NODE_TYPE_TIME_SLOT: Final[str] = "TimeSlot"

# Metadata hint keywords for domain classification (Story 2.2 code review fix #2)
# Used in classify_domain() for metadata-based domain inference
METADATA_SOCIAL_HINTS: frozenset[str] = frozenset({"family", "aunt", "uncle", "cousin", "friend"})
METADATA_PROFESSIONAL_HINTS: frozenset[str] = frozenset(
    {"colleague", "work", "boss", "client", "office"}
)

# Semantic node consolidation constants (BUG-003)
# Keywords used to identify energy-related nodes for consolidation
ENERGY_STATE_KEYWORDS: frozenset[str] = frozenset(
    {
        "energy",
        "exhaustion",
        "drain",
        "fatigue",
        "tired",
        "depleted",
        "focus",
        "concentration",
        "alertness",
        "sharpness",
        "mental",
    }
)

# RapidFuzz similarity threshold for node grouping (0-100 scale)
# Default 70 balances precision and recall:
# - Higher (80-90): fewer false merges, may miss valid groupings
# - Lower (60): more merges, may incorrectly merge distinct concepts
NODE_SIMILARITY_THRESHOLD: Final[int] = 70

# Energy keyword boost: +50 points when both labels contain energy keywords
# High boost ensures semantically related energy states (e.g., "emotional energy",
# "sharp focus", "physical energy") are grouped together even when lexically different.
# This is critical for BFS path finding in collision detection.
ENERGY_KEYWORD_BOOST: Final[int] = 50

# Graph exploration constants (Story 4.2)
# MAX_EXPLORATION_DEPTH: Maximum hops for graph visualization (vs collision detection)
# Collision detection uses MAX_DEPTH (3 hops) for cross-domain pattern finding
# Graph exploration uses a higher limit (5) but caps for terminal readability
MAX_EXPLORATION_DEPTH: Final[int] = 5
DEFAULT_EXPLORATION_DEPTH: Final[int] = 2
LARGE_GRAPH_THRESHOLD: Final[int] = 50  # Warn when neighborhood exceeds this

# HTML export default filenames (Story 4.3, 4.4)
DEFAULT_GRAPH_HTML_FILENAME: Final[str] = "sentinel-graph.html"
DEFAULT_CHECK_HTML_FILENAME: Final[str] = "sentinel-check.html"
DEFAULT_PASTE_HTML_FILENAME: Final[str] = "sentinel-paste.html"
