"""Constants for Sentinel application.

Exit codes, traversal limits, and confidence thresholds.
"""

from typing import Final

# Exit codes (following Unix conventions)
EXIT_SUCCESS: Final[int] = 0
EXIT_USER_ERROR: Final[int] = 1
EXIT_INTERNAL_ERROR: Final[int] = 2
EXIT_CONFIG_ERROR: Final[int] = 3

# Graph traversal constants
MAX_DEPTH: Final[int] = 3
DEFAULT_TIMEOUT: Final[int] = 5

# Confidence thresholds for collision scoring
HIGH_CONFIDENCE: Final[float] = 0.8
MEDIUM_CONFIDENCE: Final[float] = 0.5
