"""Tests for core constants module."""


def test_exit_codes_defined() -> None:
    """Exit codes should be defined with correct values."""
    from sentinel.core.constants import (
        EXIT_CONFIG_ERROR,
        EXIT_INTERNAL_ERROR,
        EXIT_SUCCESS,
        EXIT_USER_ERROR,
    )

    assert EXIT_SUCCESS == 0, f"Expected EXIT_SUCCESS=0, got {EXIT_SUCCESS}"
    assert EXIT_USER_ERROR == 1, f"Expected EXIT_USER_ERROR=1, got {EXIT_USER_ERROR}"
    assert EXIT_INTERNAL_ERROR == 2, f"Expected EXIT_INTERNAL_ERROR=2, got {EXIT_INTERNAL_ERROR}"
    assert EXIT_CONFIG_ERROR == 3, f"Expected EXIT_CONFIG_ERROR=3, got {EXIT_CONFIG_ERROR}"


def test_traversal_constants_defined() -> None:
    """Traversal constants should be defined with correct values."""
    from sentinel.core.constants import DEFAULT_TIMEOUT, MAX_DEPTH

    assert MAX_DEPTH == 3, f"Expected MAX_DEPTH=3, got {MAX_DEPTH}"
    assert DEFAULT_TIMEOUT == 5, f"Expected DEFAULT_TIMEOUT=5, got {DEFAULT_TIMEOUT}"


def test_confidence_thresholds_defined() -> None:
    """Confidence thresholds should be defined with correct values."""
    from sentinel.core.constants import HIGH_CONFIDENCE, MEDIUM_CONFIDENCE

    assert HIGH_CONFIDENCE == 0.8, f"Expected HIGH_CONFIDENCE=0.8, got {HIGH_CONFIDENCE}"
    assert MEDIUM_CONFIDENCE == 0.5, f"Expected MEDIUM_CONFIDENCE=0.5, got {MEDIUM_CONFIDENCE}"


def test_exit_codes_are_distinct() -> None:
    """All exit codes should be distinct values."""
    from sentinel.core.constants import (
        EXIT_CONFIG_ERROR,
        EXIT_INTERNAL_ERROR,
        EXIT_SUCCESS,
        EXIT_USER_ERROR,
    )

    codes = [EXIT_SUCCESS, EXIT_USER_ERROR, EXIT_INTERNAL_ERROR, EXIT_CONFIG_ERROR]
    assert len(codes) == len(set(codes)), "Exit codes must be distinct"


def test_confidence_thresholds_are_valid_probabilities() -> None:
    """Confidence thresholds should be valid probability values (0.0 to 1.0)."""
    from sentinel.core.constants import HIGH_CONFIDENCE, MEDIUM_CONFIDENCE

    assert 0.0 <= HIGH_CONFIDENCE <= 1.0, f"HIGH_CONFIDENCE {HIGH_CONFIDENCE} not in [0, 1]"
    assert 0.0 <= MEDIUM_CONFIDENCE <= 1.0, f"MEDIUM_CONFIDENCE {MEDIUM_CONFIDENCE} not in [0, 1]"
    assert HIGH_CONFIDENCE > MEDIUM_CONFIDENCE, "HIGH_CONFIDENCE should be > MEDIUM_CONFIDENCE"
