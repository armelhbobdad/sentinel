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
