"""Integration tests for graph persistence.

Tests end-to-end persistence scenarios using temp directories.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.constants import EXIT_SUCCESS
from sentinel.core.engine import CogneeEngine
from sentinel.core.types import Edge, Graph, Node


def _create_test_graph() -> Graph:
    """Create a graph for integration testing."""
    return Graph(
        nodes=(
            Node(
                id="person-maya",
                label="Maya",
                type="Person",
                source="user-stated",
                metadata={"cognee_type": "PERSON"},
            ),
            Node(
                id="activity-dinner",
                label="Dinner",
                type="Activity",
                source="user-stated",
                metadata={"cognee_type": "EVENT"},
            ),
            Node(
                id="person-aunt-susan",
                label="Aunt Susan",
                type="Person",
                source="user-stated",
                metadata={"cognee_type": "PERSON"},
            ),
            Node(
                id="energystate-drained",
                label="Drained",
                type="EnergyState",
                source="ai-inferred",
                metadata={"cognee_type": "EMOTION"},
            ),
        ),
        edges=(
            Edge(
                source_id="activity-dinner",
                target_id="person-aunt-susan",
                relationship="INVOLVES",
                confidence=0.9,
                metadata={"source": "user-stated"},
            ),
            Edge(
                source_id="person-aunt-susan",
                target_id="energystate-drained",
                relationship="DRAINS",
                confidence=0.75,
                metadata={"source": "ai-inferred"},
            ),
        ),
    )


class TestPasteCommandPersistence:
    """Integration tests for paste command persistence (Story 1.4 AC: #1, #5)."""

    def test_paste_creates_graph_db_file(self, tmp_path: Path) -> None:
        """paste command creates graph.db file at XDG path."""
        runner = CliRunner()
        mock_graph = _create_test_graph()

        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}),
            patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=mock_graph,
            ),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Dinner with Aunt Susan\n")

        assert result.exit_code == EXIT_SUCCESS, (
            f"Exit code: {result.exit_code}, output: {result.output}"
        )

        db_path = tmp_path / "sentinel" / "graph.db"
        assert db_path.exists(), f"graph.db should exist at {db_path}"

        # Verify it's valid JSON
        with open(db_path) as f:
            data = json.load(f)

        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 2

    def test_paste_creates_directory_structure(self, tmp_path: Path) -> None:
        """paste command creates ~/.local/share/sentinel/ directory."""
        runner = CliRunner()
        mock_graph = _create_test_graph()

        # Use a nested path that doesn't exist
        new_xdg = tmp_path / "new" / "xdg" / "data"
        assert not new_xdg.exists(), "Directory should not exist before test"

        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(new_xdg)}),
            patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=mock_graph,
            ),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

        assert result.exit_code == EXIT_SUCCESS

        sentinel_dir = new_xdg / "sentinel"
        assert sentinel_dir.exists(), "Sentinel directory should be created"
        assert sentinel_dir.is_dir(), "Should be a directory"

    def test_paste_directory_has_correct_permissions(self, tmp_path: Path) -> None:
        """paste command sets directory permissions to 700."""
        runner = CliRunner()
        mock_graph = _create_test_graph()

        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}),
            patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=mock_graph,
            ),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

        assert result.exit_code == EXIT_SUCCESS

        sentinel_dir = tmp_path / "sentinel"
        mode = sentinel_dir.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_paste_shows_save_path(self, tmp_path: Path) -> None:
        """paste command shows path where graph was saved."""
        runner = CliRunner()
        mock_graph = _create_test_graph()

        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}),
            patch(
                "sentinel.core.engine.CogneeEngine.ingest",
                new_callable=AsyncMock,
                return_value=mock_graph,
            ),
        ):
            result = runner.invoke(main, ["paste"], input="Monday: Meeting\n")

        assert result.exit_code == EXIT_SUCCESS
        # Should show path to saved file
        assert "graph.db" in result.output, f"Should show graph.db path: {result.output}"


class TestPersistenceRoundTrip:
    """Integration tests for persist/load round-trip."""

    def test_full_graph_round_trip(self, tmp_path: Path) -> None:
        """Graph survives persist/load round-trip with all data intact."""
        original = _create_test_graph()

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            engine = CogneeEngine()

            # Persist
            engine.persist(original)

            # Load
            loaded = engine.load()

        assert loaded is not None, "Should load graph"
        assert len(loaded.nodes) == len(original.nodes), "Node count should match"
        assert len(loaded.edges) == len(original.edges), "Edge count should match"

        # Verify all node IDs preserved
        original_ids = {n.id for n in original.nodes}
        loaded_ids = {n.id for n in loaded.nodes}
        assert original_ids == loaded_ids, f"Node IDs should match: {original_ids} vs {loaded_ids}"

        # Verify source labels preserved
        original_sources = {n.id: n.source for n in original.nodes}
        loaded_sources = {n.id: n.source for n in loaded.nodes}
        assert original_sources == loaded_sources, "Source labels should match"

    def test_multiple_persist_overwrites_cleanly(self, tmp_path: Path) -> None:
        """Multiple persist calls overwrite previous data cleanly."""
        graph1 = Graph(
            nodes=(Node(id="node-1", label="Node 1", type="Activity", source="user-stated"),),
            edges=(),
        )
        graph2 = Graph(
            nodes=(Node(id="node-2", label="Node 2", type="Person", source="ai-inferred"),),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            engine = CogneeEngine()

            # First persist
            engine.persist(graph1)
            loaded1 = engine.load()
            assert loaded1 is not None, "Expected graph to be loaded"
            assert loaded1.nodes[0].id == "node-1"

            # Second persist overwrites
            engine.persist(graph2)
            loaded2 = engine.load()
            assert loaded2 is not None, "Expected graph to be loaded"
            assert len(loaded2.nodes) == 1, "Should only have new graph's nodes"
            assert loaded2.nodes[0].id == "node-2"


class TestCorruptedFileIntegration:
    """Integration tests for corrupted file scenarios."""

    def test_cli_handles_corrupted_database_gracefully(self, tmp_path: Path) -> None:
        """CLI shows appropriate error for corrupted database.

        Note: This test would need a command that loads the graph,
        which is Story 2.x (check command). For now, we test engine directly.
        """
        from sentinel.core.exceptions import PersistenceError

        # Create corrupted file
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"
        db_path.write_text("this is not valid json {{{")

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            engine = CogneeEngine()
            with pytest.raises(PersistenceError) as exc_info:
                engine.load()

        assert "corrupted" in str(exc_info.value).lower()
        assert "sentinel paste" in str(exc_info.value)

    def test_valid_file_after_corrupted_fix(self, tmp_path: Path) -> None:
        """After fixing corruption by re-running paste, load works."""
        # Create corrupted file first
        sentinel_dir = tmp_path / "sentinel"
        sentinel_dir.mkdir(parents=True)
        db_path = sentinel_dir / "graph.db"
        db_path.write_text("corrupted data")

        graph = Graph(
            nodes=(Node(id="fixed", label="Fixed", type="Activity", source="user-stated"),),
            edges=(),
        )

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            engine = CogneeEngine()

            # persist() should fix the corruption
            engine.persist(graph)

            # load() should now work
            loaded = engine.load()

        assert loaded is not None
        assert loaded.nodes[0].id == "fixed"
