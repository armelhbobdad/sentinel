"""Unit tests for Acknowledgment type and AcknowledgmentStore.

Tests cover:
- Acknowledgment dataclass creation and serialization
- AcknowledgmentStore persistence (load, save, add, remove)
- Collision key generation and matching
"""

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel.core.persistence import AcknowledgmentStore, get_acks_path
from sentinel.core.rules import find_collision_by_label, generate_collision_key
from sentinel.core.types import Acknowledgment, ScoredCollision


class TestAcknowledgmentType:
    """Tests for Acknowledgment dataclass."""

    def test_acknowledgment_creation(self) -> None:
        """Acknowledgment can be created with required fields."""
        ack = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained", "focused", "Monday presentation"),
            timestamp="2026-01-21T18:00:00Z",
        )

        assert ack.collision_key == "aunt-susan"
        assert ack.node_label == "Aunt Susan"
        assert ack.path == ("Aunt Susan", "drained", "focused", "Monday presentation")
        assert ack.timestamp == "2026-01-21T18:00:00Z"

    def test_acknowledgment_frozen(self) -> None:
        """Acknowledgment is immutable (frozen)."""
        ack = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained"),
            timestamp="2026-01-21T18:00:00Z",
        )

        with pytest.raises(AttributeError):
            ack.collision_key = "modified"  # type: ignore[misc]

    def test_acknowledgment_default_timestamp(self) -> None:
        """Acknowledgment has empty string default for timestamp."""
        ack = Acknowledgment(
            collision_key="test",
            node_label="Test",
            path=("Test",),
        )

        assert ack.timestamp == ""

    def test_acknowledgment_serialization(self) -> None:
        """Acknowledgment can be serialized to dict."""
        ack = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained", "focused"),
            timestamp="2026-01-21T18:00:00Z",
        )

        data = asdict(ack)

        assert data == {
            "collision_key": "aunt-susan",
            "node_label": "Aunt Susan",
            "path": ("Aunt Susan", "drained", "focused"),
            "timestamp": "2026-01-21T18:00:00Z",
        }

    def test_acknowledgment_equality(self) -> None:
        """Two Acknowledgments with same values are equal."""
        ack1 = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained"),
            timestamp="2026-01-21T18:00:00Z",
        )
        ack2 = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained"),
            timestamp="2026-01-21T18:00:00Z",
        )

        assert ack1 == ack2

    def test_acknowledgment_hashable(self) -> None:
        """Acknowledgment is hashable (can be used in sets/dicts)."""
        ack = Acknowledgment(
            collision_key="aunt-susan",
            node_label="Aunt Susan",
            path=("Aunt Susan", "drained"),
            timestamp="2026-01-21T18:00:00Z",
        )

        # Should be hashable
        ack_set = {ack}
        assert ack in ack_set

        # Should work as dict key
        ack_dict = {ack: "value"}
        assert ack_dict[ack] == "value"


class TestGetAcksPath:
    """Tests for get_acks_path function."""

    def test_get_acks_path_returns_path(self) -> None:
        """get_acks_path returns a Path object."""
        path = get_acks_path()
        assert isinstance(path, Path)
        assert path.name == "acks.json"

    def test_get_acks_path_in_sentinel_dir(self) -> None:
        """acks.json is in sentinel directory."""
        path = get_acks_path()
        assert path.parent.name == "sentinel"


class TestAcknowledgmentStore:
    """Tests for AcknowledgmentStore persistence."""

    def test_load_returns_empty_when_file_missing(self) -> None:
        """load() returns empty list when acks.json doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with patch("sentinel.core.persistence.get_acks_path", return_value=acks_path):
                store = AcknowledgmentStore()
                acks = store.load()

                assert acks == []

    def test_add_acknowledgment_creates_file(self) -> None:
        """add_acknowledgment creates acks.json if missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack = Acknowledgment(
                    collision_key="aunt-susan",
                    node_label="Aunt Susan",
                    path=("Aunt Susan", "drained", "Monday presentation"),
                    timestamp="2026-01-21T18:00:00Z",
                )

                store = AcknowledgmentStore()
                store.add_acknowledgment(ack)

                assert acks_path.exists(), "acks.json should be created"

                with open(acks_path) as f:
                    data = json.load(f)

                assert data["version"] == "1.0"
                assert len(data["acknowledgments"]) == 1
                assert data["acknowledgments"][0]["collision_key"] == "aunt-susan"

    def test_save_uses_atomic_write(self) -> None:
        """save() uses atomic write pattern (no partial files on failure)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack = Acknowledgment(
                    collision_key="aunt-susan",
                    node_label="Aunt Susan",
                    path=("Aunt Susan", "drained"),
                    timestamp="2026-01-21T18:00:00Z",
                )

                store = AcknowledgmentStore()
                store.save([ack])

                # Verify no .tmp file left behind
                tmp_file = acks_path.with_suffix(".tmp")
                assert not tmp_file.exists(), "Temp file should be cleaned up"

    def test_load_after_save_round_trip(self) -> None:
        """load() returns what was saved."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack = Acknowledgment(
                    collision_key="aunt-susan",
                    node_label="Aunt Susan",
                    path=("Aunt Susan", "drained", "focused"),
                    timestamp="2026-01-21T18:00:00Z",
                )

                store = AcknowledgmentStore()
                store.save([ack])

                # New store instance to verify persistence
                store2 = AcknowledgmentStore()
                loaded = store2.load()

                assert len(loaded) == 1
                assert loaded[0].collision_key == "aunt-susan"
                assert loaded[0].node_label == "Aunt Susan"
                assert loaded[0].path == ("Aunt Susan", "drained", "focused")
                assert loaded[0].timestamp == "2026-01-21T18:00:00Z"

    def test_remove_acknowledgment_removes_by_key(self) -> None:
        """remove_acknowledgment removes acknowledgment by collision_key."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack1 = Acknowledgment(
                    collision_key="aunt-susan",
                    node_label="Aunt Susan",
                    path=("Aunt Susan", "drained"),
                    timestamp="2026-01-21T18:00:00Z",
                )
                ack2 = Acknowledgment(
                    collision_key="monday-meeting",
                    node_label="Monday Meeting",
                    path=("Monday Meeting", "drains"),
                    timestamp="2026-01-21T19:00:00Z",
                )

                store = AcknowledgmentStore()
                store.add_acknowledgment(ack1)
                store.add_acknowledgment(ack2)

                # Remove first acknowledgment
                result = store.remove_acknowledgment("aunt-susan")

                assert result is True
                loaded = store.load()
                assert len(loaded) == 1
                assert loaded[0].collision_key == "monday-meeting"

    def test_remove_acknowledgment_returns_false_when_not_found(self) -> None:
        """remove_acknowledgment returns False when key not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                store = AcknowledgmentStore()
                result = store.remove_acknowledgment("nonexistent")

                assert result is False

    def test_get_acknowledged_keys_returns_set(self) -> None:
        """get_acknowledged_keys returns set of collision keys."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack1 = Acknowledgment(
                    collision_key="aunt-susan",
                    node_label="Aunt Susan",
                    path=("Aunt Susan", "drained"),
                    timestamp="2026-01-21T18:00:00Z",
                )
                ack2 = Acknowledgment(
                    collision_key="monday-meeting",
                    node_label="Monday Meeting",
                    path=("Monday Meeting", "drains"),
                    timestamp="2026-01-21T19:00:00Z",
                )

                store = AcknowledgmentStore()
                store.add_acknowledgment(ack1)
                store.add_acknowledgment(ack2)

                keys = store.get_acknowledged_keys()

                assert keys == {"aunt-susan", "monday-meeting"}

    def test_load_handles_corrupted_file(self) -> None:
        """load() returns empty list when file is corrupted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"
            acks_path.write_text("not valid json {{{")

            with patch("sentinel.core.persistence.get_acks_path", return_value=acks_path):
                store = AcknowledgmentStore()
                acks = store.load()

                assert acks == []

    def test_schema_version_is_1_0(self) -> None:
        """Saved file has version 1.0."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch("sentinel.core.persistence.get_acks_path", return_value=acks_path),
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
            ):
                ack = Acknowledgment(
                    collision_key="test",
                    node_label="Test",
                    path=("Test",),
                    timestamp="2026-01-21T18:00:00Z",
                )

                store = AcknowledgmentStore()
                store.save([ack])

                with open(acks_path) as f:
                    data = json.load(f)

                assert data["version"] == "1.0"


class TestGenerateCollisionKey:
    """Tests for collision key generation."""

    def test_generate_collision_key_normalizes_label(self) -> None:
        """Collision key should be normalized: lowercase, dashes."""
        collision = ScoredCollision(
            path=("Aunt Susan", "drained", "focused", "presentation"),
            confidence=0.85,
        )

        key = generate_collision_key(collision)

        assert key == "aunt-susan", f"Expected 'aunt-susan', got '{key}'"

    def test_generate_collision_key_strips_domain_prefix(self) -> None:
        """Collision key strips domain prefix like [SOCIAL]."""
        collision = ScoredCollision(
            path=("[SOCIAL] Aunt Susan", "drained", "focused"),
            confidence=0.8,
        )

        key = generate_collision_key(collision)

        assert key == "aunt-susan", f"Expected 'aunt-susan', got '{key}'"

    def test_generate_collision_key_handles_multiple_words(self) -> None:
        """Collision key handles multiple words with spaces."""
        collision = ScoredCollision(
            path=("Monday Morning Meeting", "drains", "energy"),
            confidence=0.75,
        )

        key = generate_collision_key(collision)

        assert key == "monday-morning-meeting"

    def test_generate_collision_key_empty_path(self) -> None:
        """Collision key returns 'unknown' for empty path."""
        collision = ScoredCollision(
            path=(),
            confidence=0.5,
        )

        key = generate_collision_key(collision)

        assert key == "unknown"


class TestFindCollisionByLabel:
    """Tests for finding collisions by label."""

    def test_find_collision_exact_key_match(self) -> None:
        """find_collision_by_label finds exact key match."""
        collisions = [
            ScoredCollision(
                path=("Aunt Susan", "drained", "focused"),
                confidence=0.85,
            ),
            ScoredCollision(
                path=("Monday Meeting", "drains", "energy"),
                confidence=0.75,
            ),
        ]

        result = find_collision_by_label("aunt-susan", collisions)

        assert result is not None
        assert result.path[0] == "Aunt Susan"

    def test_find_collision_fuzzy_match(self) -> None:
        """find_collision_by_label uses fuzzy matching."""
        collisions = [
            ScoredCollision(
                path=("Aunt Susan", "drained", "focused"),
                confidence=0.85,
            ),
        ]

        # "aunt susan" (with space) should fuzzy match "Aunt Susan"
        result = find_collision_by_label("aunt susan", collisions)

        assert result is not None
        assert result.path[0] == "Aunt Susan"

    def test_find_collision_returns_none_when_not_found(self) -> None:
        """find_collision_by_label returns None when no match."""
        collisions = [
            ScoredCollision(
                path=("Aunt Susan", "drained", "focused"),
                confidence=0.85,
            ),
        ]

        result = find_collision_by_label("completely-different", collisions)

        assert result is None

    def test_find_collision_empty_list(self) -> None:
        """find_collision_by_label returns None for empty list."""
        result = find_collision_by_label("anything", [])

        assert result is None

    def test_find_collision_case_insensitive(self) -> None:
        """find_collision_by_label is case insensitive."""
        collisions = [
            ScoredCollision(
                path=("Aunt Susan", "drained"),
                confidence=0.85,
            ),
        ]

        result = find_collision_by_label("AUNT SUSAN", collisions)

        assert result is not None
        assert result.path[0] == "Aunt Susan"
