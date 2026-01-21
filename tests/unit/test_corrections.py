"""Unit tests for corrections persistence layer (Story 3.1 Task 1).

Tests CorrectionStore class and get_corrections_path() function.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

from sentinel.core.types import Correction


class TestGetCorrectionsPath:
    """Tests for get_corrections_path() function (Task 1.1)."""

    def test_returns_corrections_json_in_data_home(self) -> None:
        """Returns {data_home}/corrections.json path."""
        from sentinel.core.persistence import get_corrections_path, get_xdg_data_home

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XDG_DATA_HOME", None)
            result = get_corrections_path()

        expected = get_xdg_data_home() / "corrections.json"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_uses_custom_xdg_data_home(self, tmp_path: Path) -> None:
        """Uses custom XDG_DATA_HOME for corrections.json path."""
        from sentinel.core.persistence import get_corrections_path

        custom_xdg = str(tmp_path / "custom-data")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = get_corrections_path()

        expected = Path(custom_xdg) / "sentinel" / "corrections.json"
        assert result == expected, f"Expected {expected}, got {result}"


class TestCorrectionStoreLoad:
    """Tests for CorrectionStore.load() method (Task 1.2)."""

    def test_load_returns_empty_list_when_no_file(self, tmp_path: Path) -> None:
        """load() returns empty list when corrections.json doesn't exist."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.load()

        assert result == [], f"Expected empty list, got {result}"

    def test_load_returns_corrections_from_file(self, tmp_path: Path) -> None:
        """load() returns corrections from existing file."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        corrections_path = sentinel_dir / "corrections.json"

        # Write corrections file with schema
        data = {
            "version": "1.0",
            "corrections": [
                {
                    "node_id": "energystate-drained",
                    "action": "delete",
                    "new_value": None,
                    "timestamp": "2026-01-21T15:30:00Z",
                    "reason": "User correction: node incorrectly inferred",
                }
            ],
        }
        corrections_path.write_text(json.dumps(data), encoding="utf-8")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.load()

        assert len(result) == 1, f"Expected 1 correction, got {len(result)}"
        assert result[0].node_id == "energystate-drained", f"Expected node_id, got {result[0]}"
        assert result[0].action == "delete", f"Expected action delete, got {result[0].action}"

    def test_load_returns_empty_list_on_corrupted_file(self, tmp_path: Path) -> None:
        """load() returns empty list when file is corrupted (graceful degradation)."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        corrections_path = sentinel_dir / "corrections.json"
        corrections_path.write_text("{invalid json}", encoding="utf-8")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.load()

        assert result == [], f"Expected empty list on corrupted file, got {result}"


class TestCorrectionStoreSave:
    """Tests for CorrectionStore.save() method (Task 1.2, 1.3, 1.4)."""

    def test_save_writes_json_file_with_schema(self, tmp_path: Path) -> None:
        """save() writes valid JSON with version 1.0 schema."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        corrections = [Correction(node_id="energystate-drained", action="delete", new_value=None)]

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.save(corrections)

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        assert corrections_path.exists(), "corrections.json should exist"

        with open(corrections_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "1.0", f"Expected version 1.0, got {data.get('version')}"
        assert "corrections" in data, "Should have corrections key"
        assert len(data["corrections"]) == 1, (
            f"Should have 1 correction, got {len(data['corrections'])}"
        )

    def test_save_creates_data_directory(self, tmp_path: Path) -> None:
        """save() creates data directory if not exists."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path / "new-data")
        corrections = [Correction(node_id="test", action="delete")]

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.save(corrections)

        data_dir = tmp_path / "new-data" / "sentinel"
        assert data_dir.exists(), "Data directory should be created"

    def test_save_uses_atomic_write(self, tmp_path: Path) -> None:
        """save() uses atomic write (temp file + rename)."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        corrections1 = [Correction(node_id="node1", action="delete")]
        corrections2 = [Correction(node_id="node2", action="delete")]

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.save(corrections1)

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        first_content = corrections_path.read_text()

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store.save(corrections2)

        second_content = corrections_path.read_text()
        assert first_content != second_content, "Content should change"
        assert "node2" in second_content, "Should have new content"

        # No .tmp file should remain
        tmp_file = corrections_path.with_suffix(".tmp")
        assert not tmp_file.exists(), "Temp file should be cleaned up"

    def test_save_includes_timestamp(self, tmp_path: Path) -> None:
        """save() includes timestamp in correction records."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        corrections = [Correction(node_id="test", action="delete")]

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.save(corrections)

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        with open(corrections_path, encoding="utf-8") as f:
            data = json.load(f)

        correction_data = data["corrections"][0]
        assert "timestamp" in correction_data, "Should have timestamp"
        # Verify ISO format with Z suffix
        assert correction_data["timestamp"].endswith("Z"), "Timestamp should be UTC"


class TestCorrectionStoreAddCorrection:
    """Tests for CorrectionStore.add_correction() method (Task 1.2)."""

    def test_add_correction_appends_to_existing(self, tmp_path: Path) -> None:
        """add_correction() appends new correction and persists."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            # Add first correction
            store.add_correction(
                Correction(node_id="node1", action="delete"),
                reason="Test reason 1",
            )
            # Add second correction
            store.add_correction(
                Correction(node_id="node2", action="delete"),
                reason="Test reason 2",
            )

            # Verify both are persisted
            result = store.load()

        assert len(result) == 2, f"Expected 2 corrections, got {len(result)}"
        assert result[0].node_id == "node1", f"First should be node1, got {result[0].node_id}"
        assert result[1].node_id == "node2", f"Second should be node2, got {result[1].node_id}"

    def test_add_correction_includes_reason(self, tmp_path: Path) -> None:
        """add_correction() stores the reason in the correction record."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        reason = "User correction: incorrectly inferred node"

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.add_correction(Correction(node_id="test", action="delete"), reason=reason)

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        with open(corrections_path, encoding="utf-8") as f:
            data = json.load(f)

        correction_data = data["corrections"][0]
        assert correction_data["reason"] == reason, f"Expected reason, got {correction_data}"


class TestCorrectionStoreGetDeletedNodeIds:
    """Tests for CorrectionStore.get_deleted_node_ids() method."""

    def test_get_deleted_node_ids_returns_set(self, tmp_path: Path) -> None:
        """get_deleted_node_ids() returns set of deleted node IDs."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.add_correction(Correction(node_id="node1", action="delete"))
            store.add_correction(Correction(node_id="node2", action="modify", new_value="new"))
            store.add_correction(Correction(node_id="node3", action="delete"))

            result = store.get_deleted_node_ids()

        assert result == {"node1", "node3"}, f"Expected deleted IDs, got {result}"

    def test_get_deleted_node_ids_empty_when_no_deletions(self, tmp_path: Path) -> None:
        """get_deleted_node_ids() returns empty set when no deletions."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.get_deleted_node_ids()

        assert result == set(), f"Expected empty set, got {result}"


# Story 3-2: Extended Correction type tests


class TestCorrectionTypeExtended:
    """Tests for extended Correction type with edge operation fields (Story 3-2 Task 1)."""

    def test_correction_has_target_node_id_field(self) -> None:
        """Correction type has optional target_node_id field for edge operations."""
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
        )

        assert correction.target_node_id == "energystate-drained", (
            f"Expected target_node_id, got {correction.target_node_id}"
        )

    def test_correction_has_edge_relationship_field(self) -> None:
        """Correction type has optional edge_relationship field for original relationship."""
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
            edge_relationship="DRAINS",
        )

        assert correction.edge_relationship == "DRAINS", (
            f"Expected edge_relationship, got {correction.edge_relationship}"
        )

    def test_correction_optional_fields_default_none(self) -> None:
        """Optional fields default to None for backward compatibility."""
        correction = Correction(node_id="test", action="delete")

        assert correction.target_node_id is None, "target_node_id should default to None"
        assert correction.edge_relationship is None, "edge_relationship should default to None"

    def test_correction_immutable_with_new_fields(self) -> None:
        """Correction remains immutable with new fields."""
        correction = Correction(
            node_id="person-aunt-susan",
            action="remove_edge",
            target_node_id="energystate-drained",
            edge_relationship="DRAINS",
        )

        # Should raise FrozenInstanceError (or similar) on modification attempt
        import pytest

        with pytest.raises(Exception):  # FrozenInstanceError
            correction.target_node_id = "other"  # type: ignore[misc]


class TestCorrectionStoreSchemav11:
    """Tests for CorrectionStore schema v1.1 with edge corrections (Story 3-2 Task 1.3)."""

    def test_save_edge_correction_includes_new_fields(self, tmp_path: Path) -> None:
        """save() includes target_node_id and edge_relationship for edge corrections."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        correction = Correction(
            node_id="person-aunt-susan",
            action="modify_relationship",
            new_value="ENERGIZES",
            target_node_id="energystate-drained",
            edge_relationship="DRAINS",
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.add_correction(correction, reason="Changed DRAINS to ENERGIZES")

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        with open(corrections_path, encoding="utf-8") as f:
            data = json.load(f)

        # Schema v1.1 should be used when edge fields are present
        assert data["version"] == "1.1", f"Expected version 1.1, got {data.get('version')}"

        correction_data = data["corrections"][0]
        assert correction_data["target_node_id"] == "energystate-drained", (
            f"Expected target_node_id, got {correction_data}"
        )
        assert correction_data["edge_relationship"] == "DRAINS", (
            f"Expected edge_relationship, got {correction_data}"
        )

    def test_load_v11_corrections_with_edge_fields(self, tmp_path: Path) -> None:
        """load() correctly parses v1.1 schema with edge correction fields."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        corrections_path = sentinel_dir / "corrections.json"

        # Write v1.1 schema with edge correction
        data = {
            "version": "1.1",
            "corrections": [
                {
                    "node_id": "person-aunt-susan",
                    "action": "modify_relationship",
                    "new_value": "ENERGIZES",
                    "target_node_id": "energystate-drained",
                    "edge_relationship": "DRAINS",
                    "timestamp": "2026-01-21T16:30:00Z",
                    "reason": "User changed relationship",
                }
            ],
        }
        corrections_path.write_text(json.dumps(data), encoding="utf-8")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.load()

        assert len(result) == 1, f"Expected 1 correction, got {len(result)}"
        assert result[0].target_node_id == "energystate-drained", (
            f"Expected target_node_id, got {result[0].target_node_id}"
        )
        assert result[0].edge_relationship == "DRAINS", (
            f"Expected edge_relationship, got {result[0].edge_relationship}"
        )

    def test_load_v10_backward_compatibility(self, tmp_path: Path) -> None:
        """load() still works with v1.0 schema (backward compatibility)."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        corrections_path = sentinel_dir / "corrections.json"

        # Write v1.0 schema (no edge fields)
        data = {
            "version": "1.0",
            "corrections": [
                {
                    "node_id": "energystate-drained",
                    "action": "delete",
                    "new_value": None,
                    "timestamp": "2026-01-21T15:30:00Z",
                    "reason": "User deleted node",
                }
            ],
        }
        corrections_path.write_text(json.dumps(data), encoding="utf-8")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            result = store.load()

        assert len(result) == 1, f"Expected 1 correction, got {len(result)}"
        assert result[0].node_id == "energystate-drained"
        assert result[0].action == "delete"
        # New fields should default to None
        assert result[0].target_node_id is None, "target_node_id should be None for v1.0"
        assert result[0].edge_relationship is None, "edge_relationship should be None for v1.0"

    def test_save_uses_v10_when_no_edge_corrections(self, tmp_path: Path) -> None:
        """save() uses v1.0 schema when no edge corrections are present."""
        from sentinel.core.persistence import CorrectionStore

        custom_xdg = str(tmp_path)
        correction = Correction(node_id="test", action="delete")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            store = CorrectionStore()
            store.add_correction(correction, reason="Deleted node")

        corrections_path = tmp_path / "sentinel" / "corrections.json"
        with open(corrections_path, encoding="utf-8") as f:
            data = json.load(f)

        # Should still use v1.0 for node-only corrections (backward compatibility)
        assert data["version"] == "1.0", f"Expected version 1.0, got {data.get('version')}"
