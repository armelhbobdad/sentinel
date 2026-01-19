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
