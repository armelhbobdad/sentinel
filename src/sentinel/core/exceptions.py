"""Custom exceptions for Sentinel.

All Sentinel-specific exceptions inherit from SentinelError.
"""


class SentinelError(Exception):
    """Base exception for Sentinel errors."""

    pass


class IngestionError(SentinelError):
    """Error during schedule text ingestion via Cognee.

    Raised when the Cognee API fails due to network errors,
    timeouts, or invalid API responses.
    """

    pass


class PersistenceError(SentinelError):
    """Error during graph persistence operations.

    Raised when saving or loading the graph database fails
    due to I/O errors or corrupted data.
    """

    pass
