"""Persistence utilities for Sentinel graphs.

Provides XDG-compliant path handling and graph serialization/deserialization.
All data is stored in ~/.local/share/sentinel/ by default, respecting
the XDG_DATA_HOME environment variable when set.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from sentinel.core.types import Correction

logger = logging.getLogger(__name__)


def get_xdg_data_home() -> Path:
    """Get XDG data home directory for Sentinel.

    Returns ~/.local/share/sentinel/ by default.
    Respects XDG_DATA_HOME environment variable when set.

    Returns:
        Path to Sentinel's data directory.
    """
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        base = Path(xdg_data_home)
    else:
        base = Path.home() / ".local" / "share"
    return base / "sentinel"


def get_graph_db_path() -> Path:
    """Get path to graph database file.

    Returns:
        Path to graph.db file within Sentinel's data directory.
    """
    return get_xdg_data_home() / "graph.db"


def ensure_data_directory() -> Path:
    """Ensure data directory exists with correct permissions.

    Creates the directory with mkdir -p behavior if it doesn't exist.
    Sets permissions to 700 (owner only) for security.

    Returns:
        Path to the created/existing data directory.
    """
    data_dir = get_xdg_data_home()
    data_dir.mkdir(parents=True, exist_ok=True)
    # Set permissions to owner only (700)
    data_dir.chmod(0o700)
    return data_dir


def get_corrections_path() -> Path:
    """Get path to corrections file.

    Returns:
        Path to corrections.json file within Sentinel's data directory.
    """
    return get_xdg_data_home() / "corrections.json"


class CorrectionStore:
    """Persistence layer for user corrections to the graph.

    Manages loading, saving, and adding corrections to a JSON file.
    Uses atomic write pattern (temp file + rename) to prevent corruption.

    Corrections file schema (version 1.0):
    {
        "version": "1.0",
        "corrections": [
            {
                "node_id": "energystate-drained",
                "action": "delete",
                "new_value": null,
                "timestamp": "2026-01-21T15:30:00Z",
                "reason": "User correction: node incorrectly inferred"
            }
        ]
    }
    """

    def __init__(self) -> None:
        """Initialize CorrectionStore."""
        self._corrections: list[Correction] = []
        self._loaded = False

    def load(self) -> list[Correction]:
        """Load corrections from the corrections file.

        Supports both v1.0 (node corrections only) and v1.1 (with edge corrections).

        Returns:
            List of corrections. Empty list if file doesn't exist or is corrupted.
        """
        corrections_path = get_corrections_path()

        if not corrections_path.exists():
            self._corrections = []
            self._loaded = True
            return []

        try:
            with open(corrections_path, encoding="utf-8") as f:
                data = json.load(f)

            corrections = []
            for item in data.get("corrections", []):
                corrections.append(
                    Correction(
                        node_id=item["node_id"],
                        action=item["action"],
                        new_value=item.get("new_value"),
                        # v1.1 edge fields (default to None for backward compatibility)
                        target_node_id=item.get("target_node_id"),
                        edge_relationship=item.get("edge_relationship"),
                    )
                )

            self._corrections = corrections
            self._loaded = True
            return corrections

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Graceful degradation: return empty list on corrupted file
            logger.warning("Corrections file corrupted, ignoring: %s", e)
            self._corrections = []
            self._loaded = True
            return []

    def save(self, corrections: list[Correction]) -> None:
        """Save corrections to the corrections file.

        Uses atomic write (temp file + rename) to prevent corruption.
        Uses schema v1.1 when any correction has edge fields, v1.0 otherwise.

        Args:
            corrections: List of corrections to save.
        """
        ensure_data_directory()
        corrections_path = get_corrections_path()

        # Load existing data to preserve timestamps and reasons
        existing_data: dict[str, dict] = {}
        if corrections_path.exists():
            try:
                with open(corrections_path, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("corrections", []):
                    # Use composite key for edge corrections
                    key = self._correction_key(item)
                    existing_data[key] = item
            except (json.JSONDecodeError, KeyError, TypeError):
                pass  # Ignore corrupted existing file

        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Determine schema version: v1.1 if any correction has edge fields
        has_edge_corrections = any(
            c.target_node_id is not None or c.edge_relationship is not None for c in corrections
        )
        schema_version = "1.1" if has_edge_corrections else "1.0"

        correction_records = []
        for correction in corrections:
            # Preserve existing timestamp and reason if available
            key = self._correction_key_from_obj(correction)
            existing = existing_data.get(key, {})
            record: dict = {
                "node_id": correction.node_id,
                "action": correction.action,
                "new_value": correction.new_value,
                "timestamp": existing.get("timestamp", now),
                "reason": existing.get("reason", ""),
            }
            # Include edge fields for v1.1 schema
            if has_edge_corrections:
                record["target_node_id"] = correction.target_node_id
                record["edge_relationship"] = correction.edge_relationship
            correction_records.append(record)

        data = {
            "version": schema_version,
            "corrections": correction_records,
        }

        # Atomic write: write to temp, then rename
        temp_path = corrections_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(corrections_path)  # Atomic on POSIX
        finally:
            # Clean up temp file if it still exists
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass  # Best effort cleanup

        self._corrections = corrections

    def _correction_key(self, item: dict) -> str:
        """Generate unique key for a correction record dict."""
        node_id = item.get("node_id", "")
        target_id = item.get("target_node_id", "")
        if target_id:
            return f"{node_id}:{target_id}"
        return node_id

    def _correction_key_from_obj(self, correction: Correction) -> str:
        """Generate unique key for a Correction object."""
        if correction.target_node_id:
            return f"{correction.node_id}:{correction.target_node_id}"
        return correction.node_id

    def add_correction(self, correction: Correction, reason: str = "") -> None:
        """Add a new correction and persist immediately.

        Uses schema v1.1 when any correction has edge fields, v1.0 otherwise.

        Args:
            correction: The correction to add.
            reason: Human-readable reason for the correction.
        """
        # Ensure we have current state loaded
        if not self._loaded:
            self.load()

        # Add the new correction
        self._corrections.append(correction)

        # Persist with the new reason
        ensure_data_directory()
        corrections_path = get_corrections_path()

        # Load existing data to preserve other timestamps
        existing_data: dict[str, dict] = {}
        if corrections_path.exists():
            try:
                with open(corrections_path, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("corrections", []):
                    key = self._correction_key(item)
                    existing_data[key] = item
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Determine schema version: v1.1 if any correction has edge fields
        has_edge_corrections = any(
            c.target_node_id is not None or c.edge_relationship is not None
            for c in self._corrections
        )
        schema_version = "1.1" if has_edge_corrections else "1.0"

        correction_records = []
        for corr in self._corrections:
            key = self._correction_key_from_obj(corr)
            existing = existing_data.get(key, {})
            # Use the new reason for the newly added correction
            if corr is correction:
                record: dict = {
                    "node_id": corr.node_id,
                    "action": corr.action,
                    "new_value": corr.new_value,
                    "timestamp": now,
                    "reason": reason,
                }
            else:
                record = {
                    "node_id": corr.node_id,
                    "action": corr.action,
                    "new_value": corr.new_value,
                    "timestamp": existing.get("timestamp", now),
                    "reason": existing.get("reason", ""),
                }
            # Include edge fields for v1.1 schema
            if has_edge_corrections:
                record["target_node_id"] = corr.target_node_id
                record["edge_relationship"] = corr.edge_relationship
            correction_records.append(record)

        data = {
            "version": schema_version,
            "corrections": correction_records,
        }

        # Atomic write
        temp_path = corrections_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(corrections_path)
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass

    def get_deleted_node_ids(self) -> set[str]:
        """Get set of node IDs that have been deleted.

        Returns:
            Set of node IDs with action="delete".
        """
        if not self._loaded:
            self.load()

        return {c.node_id for c in self._corrections if c.action == "delete"}

    def load_records(self) -> list[dict]:
        """Load corrections with full metadata including timestamps.

        Returns:
            List of correction records as dicts with node_id, action,
            new_value, timestamp, and reason fields.
        """
        corrections_path = get_corrections_path()

        if not corrections_path.exists():
            return []

        try:
            with open(corrections_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("corrections", [])
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
