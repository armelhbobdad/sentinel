"""Unit tests for persistence utilities.

Tests XDG path handling and graph serialization/deserialization.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel.core.types import Edge, Graph, Node


class TestGetXdgDataHome:
    """Tests for get_xdg_data_home() function."""

    def test_default_path_without_xdg_env(self) -> None:
        """Returns ~/.local/share/sentinel/ when XDG_DATA_HOME not set."""
        from sentinel.core.persistence import get_xdg_data_home

        with patch.dict(os.environ, {}, clear=True):
            # Remove XDG_DATA_HOME if present
            os.environ.pop("XDG_DATA_HOME", None)
            result = get_xdg_data_home()

        expected = Path.home() / ".local" / "share" / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_respects_xdg_data_home_env(self, tmp_path: Path) -> None:
        """Uses XDG_DATA_HOME environment variable when set."""
        from sentinel.core.persistence import get_xdg_data_home

        custom_xdg = str(tmp_path / "custom-xdg")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = get_xdg_data_home()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"


class TestGetGraphDbPath:
    """Tests for get_graph_db_path() function."""

    def test_returns_graph_db_in_data_home(self) -> None:
        """Returns {data_home}/graph.db path."""
        from sentinel.core.persistence import get_graph_db_path, get_xdg_data_home

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XDG_DATA_HOME", None)
            result = get_graph_db_path()

        expected = get_xdg_data_home() / "graph.db"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_uses_custom_xdg_data_home(self, tmp_path: Path) -> None:
        """Uses custom XDG_DATA_HOME for graph.db path."""
        from sentinel.core.persistence import get_graph_db_path

        custom_xdg = str(tmp_path / "custom-data")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = get_graph_db_path()

        expected = Path(custom_xdg) / "sentinel" / "graph.db"
        assert result == expected, f"Expected {expected}, got {result}"


class TestEnsureDataDirectory:
    """Tests for ensure_data_directory() function."""

    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Creates data directory with mkdir -p behavior."""
        from sentinel.core.persistence import ensure_data_directory

        custom_xdg = str(tmp_path / "new-xdg-data")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = ensure_data_directory()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"
        assert result.exists(), "Directory should exist"
        assert result.is_dir(), "Should be a directory"

    def test_sets_directory_permissions_700(self, tmp_path: Path) -> None:
        """Sets directory permissions to 700 (owner only)."""
        from sentinel.core.persistence import ensure_data_directory

        custom_xdg = str(tmp_path / "secure-xdg")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = ensure_data_directory()

        # Check permissions (700 = rwx------)
        mode = result.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_idempotent_when_directory_exists(self, tmp_path: Path) -> None:
        """Returns existing directory without error."""
        from sentinel.core.persistence import ensure_data_directory

        custom_xdg = str(tmp_path / "existing-xdg")
        sentinel_dir = Path(custom_xdg) / "sentinel"
        sentinel_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = ensure_data_directory()

        assert result == sentinel_dir, f"Expected {sentinel_dir}, got {result}"
        assert result.exists(), "Directory should still exist"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates all parent directories (mkdir -p behavior)."""
        from sentinel.core.persistence import ensure_data_directory

        custom_xdg = str(tmp_path / "deep" / "nested" / "xdg")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            result = ensure_data_directory()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"
        assert result.exists(), "Directory should exist"


class TestCogneeEnginePersist:
    """Tests for CogneeEngine.persist() method."""

    def test_persist_writes_json_file(self, tmp_path: Path) -> None:
        """persist() writes valid JSON file to graph.db."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph = Graph(
            nodes=(
                Node(
                    id="person-maya",
                    label="Maya",
                    type="Person",
                    source="user-stated",
                    metadata={"cognee_type": "PERSON"},
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        assert db_path.exists(), "graph.db should exist"

        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "nodes" in data, "JSON should have nodes key"
        assert "edges" in data, "JSON should have edges key"
        assert "version" in data, "JSON should have version key"
        assert len(data["nodes"]) == 1, "Should have 1 node"

    def test_persist_serializes_node_correctly(self, tmp_path: Path) -> None:
        """persist() serializes Node with all fields."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph = Graph(
            nodes=(
                Node(
                    id="person-aunt-susan",
                    label="Aunt Susan",
                    type="Person",
                    source="user-stated",
                    metadata={"cognee_type": "PERSON", "extra": "value"},
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        node = data["nodes"][0]
        assert node["id"] == "person-aunt-susan", f"Expected id, got {node}"
        assert node["label"] == "Aunt Susan", f"Expected label, got {node}"
        assert node["type"] == "Person", f"Expected type, got {node}"
        assert node["source"] == "user-stated", f"Expected source, got {node}"
        assert node["metadata"]["cognee_type"] == "PERSON", f"Expected metadata, got {node}"

    def test_persist_serializes_edge_correctly(self, tmp_path: Path) -> None:
        """persist() serializes Edge with all fields."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.85,
                    metadata={"cognee_type": "drains"},
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        edge = data["edges"][0]
        assert edge["source_id"] == "person-maya", f"Expected source_id, got {edge}"
        assert edge["target_id"] == "energystate-drained", f"Expected target_id, got {edge}"
        assert edge["relationship"] == "DRAINS", f"Expected relationship, got {edge}"
        assert edge["confidence"] == 0.85, f"Expected confidence, got {edge}"

    def test_persist_creates_data_directory(self, tmp_path: Path) -> None:
        """persist() creates data directory if not exists."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path / "new-data")
        graph = Graph(nodes=(), edges=())

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        data_dir = tmp_path / "new-data" / "sentinel"
        assert data_dir.exists(), "Data directory should be created"

    def test_persist_atomic_write(self, tmp_path: Path) -> None:
        """persist() uses atomic write (temp file + rename)."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph = Graph(
            nodes=(Node(id="test", label="Test", type="Activity", source="user-stated"),),
            edges=(),
        )

        # First persist
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        first_content = db_path.read_text()

        # Second persist should overwrite atomically
        graph2 = Graph(
            nodes=(Node(id="test2", label="Test2", type="Activity", source="ai-inferred"),),
            edges=(),
        )
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine.persist(graph2)

        second_content = db_path.read_text()
        assert first_content != second_content, "Content should change"
        assert "test2" in second_content, "Should have new content"

    def test_persist_includes_timestamps(self, tmp_path: Path) -> None:
        """persist() includes created_at and updated_at timestamps."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph = Graph(nodes=(), edges=())

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph)

        db_path = tmp_path / "sentinel" / "graph.db"
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "created_at" in data, "Should have created_at"
        assert "updated_at" in data, "Should have updated_at"
        # Verify ISO format with Z suffix
        assert data["created_at"].endswith("Z"), "created_at should be UTC"
        assert data["updated_at"].endswith("Z"), "updated_at should be UTC"

    def test_persist_preserves_created_at_on_update(self, tmp_path: Path) -> None:
        """persist() preserves original created_at when updating (M4 fix)."""
        import time

        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        graph1 = Graph(nodes=(), edges=())

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(graph1)

        db_path = tmp_path / "sentinel" / "graph.db"
        with open(db_path, encoding="utf-8") as f:
            data1 = json.load(f)
        original_created_at = data1["created_at"]

        # Wait a tiny bit to ensure timestamps differ
        time.sleep(0.01)

        # Persist again
        graph2 = Graph(
            nodes=(Node(id="new", label="New", type="Activity", source="user-stated"),),
            edges=(),
        )
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine.persist(graph2)

        with open(db_path, encoding="utf-8") as f:
            data2 = json.load(f)

        assert data2["created_at"] == original_created_at, (
            f"created_at should be preserved: {data2['created_at']} != {original_created_at}"
        )
        assert data2["updated_at"] != original_created_at, (
            "updated_at should be different from original"
        )


class TestCogneeEngineLoad:
    """Tests for CogneeEngine.load() method."""

    def test_load_returns_none_when_no_file(self, tmp_path: Path) -> None:
        """load() returns None when graph.db doesn't exist."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            result = engine.load()

        assert result is None, "Should return None when file doesn't exist"

    def test_empty_graph_round_trip(self, tmp_path: Path) -> None:
        """Empty graph survives persist/load round-trip (M5 fix)."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(nodes=(), edges=())

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        assert loaded is not None, "Should load graph"
        assert loaded.nodes == (), "Should have empty nodes tuple"
        assert loaded.edges == (), "Should have empty edges tuple"

    def test_load_returns_graph_from_persisted_file(self, tmp_path: Path) -> None:
        """load() returns Graph from previously persisted file."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(Node(id="person-maya", label="Maya", type="Person", source="user-stated"),),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        assert loaded is not None, "Should return Graph"
        assert len(loaded.nodes) == 1, "Should have 1 node"
        assert loaded.nodes[0].id == "person-maya", f"Expected id, got {loaded.nodes[0].id}"
        assert loaded.nodes[0].label == "Maya", f"Expected label, got {loaded.nodes[0].label}"

    def test_load_reconstructs_node_correctly(self, tmp_path: Path) -> None:
        """load() reconstructs Node with all fields."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(
                Node(
                    id="person-aunt-susan",
                    label="Aunt Susan",
                    type="Person",
                    source="user-stated",
                    metadata={"cognee_type": "PERSON", "extra": "value"},
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        node = loaded.nodes[0]
        assert node.id == "person-aunt-susan", f"Expected id, got {node.id}"
        assert node.label == "Aunt Susan", f"Expected label, got {node.label}"
        assert node.type == "Person", f"Expected type, got {node.type}"
        assert node.source == "user-stated", f"Expected source, got {node.source}"
        assert node.metadata.get("cognee_type") == "PERSON", (
            f"Expected metadata, got {node.metadata}"
        )

    def test_load_reconstructs_edge_correctly(self, tmp_path: Path) -> None:
        """load() reconstructs Edge with all fields."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.85,
                    metadata={"cognee_type": "drains"},
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        assert len(loaded.edges) == 1, "Should have 1 edge"
        edge = loaded.edges[0]
        assert edge.source_id == "person-maya", f"Expected source_id, got {edge.source_id}"
        assert edge.target_id == "energystate-drained", f"Expected target_id, got {edge.target_id}"
        assert edge.relationship == "DRAINS", f"Expected relationship, got {edge.relationship}"
        assert edge.confidence == 0.85, f"Expected confidence, got {edge.confidence}"

    def test_load_preserves_source_labels_round_trip(self, tmp_path: Path) -> None:
        """load() preserves source labels through persist/load round-trip."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-tired",
                    label="Tired",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        # Find nodes by id
        maya = next(n for n in loaded.nodes if n.id == "person-maya")
        tired = next(n for n in loaded.nodes if n.id == "energystate-tired")

        assert maya.source == "user-stated", f"Maya source should be user-stated, got {maya.source}"
        assert tired.source == "ai-inferred", (
            f"Tired source should be ai-inferred, got {tired.source}"
        )

    def test_load_preserves_edge_metadata_source(self, tmp_path: Path) -> None:
        """load() preserves edge metadata source through round-trip (AC #4)."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(
                Node(id="person-maya", label="Maya", type="Person", source="user-stated"),
                Node(
                    id="energystate-drained",
                    label="Drained",
                    type="EnergyState",
                    source="ai-inferred",
                ),
            ),
            edges=(
                Edge(
                    source_id="person-maya",
                    target_id="energystate-drained",
                    relationship="DRAINS",
                    confidence=0.85,
                    metadata={"source": "ai-inferred", "cognee_type": "drains"},
                ),
            ),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        edge = loaded.edges[0]
        assert edge.metadata.get("source") == "ai-inferred", (
            f"Edge metadata source should be ai-inferred, got {edge.metadata}"
        )

    def test_load_preserves_node_cognee_metadata(self, tmp_path: Path) -> None:
        """load() preserves cognee_type and custom metadata through round-trip."""
        from sentinel.core.engine import CogneeEngine

        custom_xdg = str(tmp_path)
        original = Graph(
            nodes=(
                Node(
                    id="person-maya",
                    label="Maya",
                    type="Person",
                    source="user-stated",
                    metadata={"cognee_type": "PERSON", "custom_field": "custom_value"},
                ),
            ),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            engine.persist(original)
            loaded = engine.load()

        node = loaded.nodes[0]
        assert node.metadata.get("cognee_type") == "PERSON", (
            f"cognee_type should be preserved, got {node.metadata}"
        )
        assert node.metadata.get("custom_field") == "custom_value", (
            f"custom_field should be preserved, got {node.metadata}"
        )


class TestCorruptedDatabaseHandling:
    """Tests for corrupted database handling (Story 1.4 AC: #6)."""

    def test_persistence_error_inherits_from_sentinel_error(self) -> None:
        """PersistenceError should inherit from SentinelError (L3 fix)."""
        from sentinel.core.exceptions import PersistenceError, SentinelError

        assert issubclass(PersistenceError, SentinelError), (
            "PersistenceError should inherit from SentinelError"
        )
        # Also verify instance check works
        err = PersistenceError("test")
        assert isinstance(err, SentinelError), (
            "PersistenceError instance should be SentinelError instance"
        )

    def test_load_raises_persistence_error_on_invalid_json(self, tmp_path: Path) -> None:
        """load() raises PersistenceError on invalid JSON."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.exceptions import PersistenceError

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"

        # Write invalid JSON
        db_path.write_text("{invalid json}")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        assert "corrupted" in str(exc_info.value).lower(), (
            f"Expected 'corrupted' in error: {exc_info.value}"
        )
        assert "sentinel paste" in str(exc_info.value), (
            f"Expected rebuild instruction: {exc_info.value}"
        )

    def test_load_raises_persistence_error_on_missing_keys(self, tmp_path: Path) -> None:
        """load() raises PersistenceError on JSON with missing required keys."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.exceptions import PersistenceError

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"

        # Write JSON with missing required node keys
        db_path.write_text('{"nodes": [{"id": "test"}], "edges": []}')

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        assert "corrupted" in str(exc_info.value).lower(), (
            f"Expected 'corrupted' in error: {exc_info.value}"
        )

    def test_load_raises_persistence_error_on_truncated_file(self, tmp_path: Path) -> None:
        """load() raises PersistenceError on truncated/incomplete JSON."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.exceptions import PersistenceError

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"

        # Write truncated JSON
        db_path.write_text('{"nodes": [{"id": "test", "label": "Test"')

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        assert "corrupted" in str(exc_info.value).lower(), (
            f"Expected 'corrupted' in error: {exc_info.value}"
        )

    def test_load_raises_persistence_error_on_wrong_type(self, tmp_path: Path) -> None:
        """load() raises PersistenceError on JSON with wrong data types."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.exceptions import PersistenceError

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"

        # Write JSON with wrong types (nodes should be array, not string)
        db_path.write_text('{"nodes": "not an array", "edges": []}')

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        assert "corrupted" in str(exc_info.value).lower(), (
            f"Expected 'corrupted' in error: {exc_info.value}"
        )

    def test_persistence_error_message_exact_text(self, tmp_path: Path) -> None:
        """PersistenceError contains exact error message per AC #6."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.exceptions import PersistenceError

        custom_xdg = str(tmp_path)
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"
        db_path.write_text("not json at all")

        with patch.dict(os.environ, {"XDG_DATA_HOME": custom_xdg}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        expected = "Graph database corrupted. Run `sentinel paste` to rebuild."
        assert str(exc_info.value) == expected, f"Expected exact message: {exc_info.value}"
