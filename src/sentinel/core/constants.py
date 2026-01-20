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
HIGH_CONFIDENCE: Final[float] = 0.8
MEDIUM_CONFIDENCE: Final[float] = 0.5

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
