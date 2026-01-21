"""Unit tests for CLI ack command.

Tests cover:
- ack <label>: Acknowledge a collision warning
- ack --list: List acknowledged collisions
- ack --remove <label>: Remove an acknowledgment
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.types import Edge, Graph, Node, ScoredCollision


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_graph() -> Graph:
    """Create a sample graph with potential collisions."""
    nodes = (
        Node(
            id="person-aunt-susan",
            label="Aunt Susan",
            type="Person",
            source="ai-inferred",
            metadata={"domain": "SOCIAL"},
        ),
        Node(
            id="activity-visiting",
            label="Visiting Aunt Susan",
            type="Activity",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="energystate-drained",
            label="Drained",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="energystate-focused",
            label="Focused",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="timeslot-presentation",
            label="Monday presentation",
            type="TimeSlot",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
    )
    edges = (
        Edge(
            source_id="activity-visiting",
            target_id="energystate-drained",
            relationship="DRAINS",
            confidence=0.9,
            metadata={},
        ),
        Edge(
            source_id="energystate-drained",
            target_id="energystate-focused",
            relationship="CONFLICTS_WITH",
            confidence=0.85,
            metadata={},
        ),
        Edge(
            source_id="timeslot-presentation",
            target_id="energystate-focused",
            relationship="REQUIRES",
            confidence=0.9,
            metadata={},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


@pytest.fixture
def sample_collisions() -> list[ScoredCollision]:
    """Create sample collisions for testing."""
    return [
        ScoredCollision(
            path=(
                "[SOCIAL] Aunt Susan",
                "DRAINS",
                "Drained",
                "CONFLICTS_WITH",
                "Focused",
                "REQUIRES",
                "Monday presentation",
            ),
            confidence=0.85,
            source_breakdown={"ai_inferred": 4, "user_stated": 1},
        ),
    ]


class TestAckCommand:
    """Tests for ack command - acknowledge collisions."""

    def test_ack_no_label(self, cli_runner: CliRunner) -> None:
        """ack with no arguments shows error."""
        result = cli_runner.invoke(main, ["ack"])

        assert result.exit_code != 0
        assert "No label provided" in result.output

    def test_ack_no_graph(self, cli_runner: CliRunner) -> None:
        """ack shows error when no graph exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=Path(tmp_dir),
            ):
                result = cli_runner.invoke(main, ["ack", "aunt-susan"])

                assert result.exit_code != 0
                assert "No schedule data found" in result.output

    def test_ack_no_collisions(self, cli_runner: CliRunner, sample_graph: Graph) -> None:
        """ack shows error when no collisions exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=[],
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                result = cli_runner.invoke(main, ["ack", "aunt-susan"])

                assert result.exit_code != 0
                assert "No collisions detected" in result.output

    def test_ack_acknowledges_collision(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
    ) -> None:
        """ack acknowledges matching collision and persists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=sample_collisions,
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                result = cli_runner.invoke(main, ["ack", "aunt-susan"])

                assert result.exit_code == 0
                assert "Acknowledged" in result.output

                # Verify acknowledgment was persisted
                assert acks_path.exists()
                with open(acks_path) as f:
                    data = json.load(f)
                assert len(data["acknowledgments"]) == 1
                assert data["acknowledgments"][0]["collision_key"] == "aunt-susan"

    def test_ack_fuzzy_match(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
    ) -> None:
        """ack uses fuzzy matching for labels."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=sample_collisions,
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                # Use space instead of dash
                result = cli_runner.invoke(main, ["ack", "aunt susan"])

                assert result.exit_code == 0
                assert "Acknowledged" in result.output

    def test_ack_not_found(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
    ) -> None:
        """ack shows error when collision not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=sample_collisions,
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                result = cli_runner.invoke(main, ["ack", "completely-wrong"])

                assert result.exit_code != 0
                assert "No collision found involving" in result.output


class TestAckListCommand:
    """Tests for ack --list command."""

    def test_ack_list_empty(self, cli_runner: CliRunner) -> None:
        """ack --list shows message when no acknowledgments exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=Path(tmp_dir) / "acks.json",
                ),
            ):
                result = cli_runner.invoke(main, ["ack", "--list"])

                assert result.exit_code == 0
                assert "No acknowledgments" in result.output

    def test_ack_list_shows_acknowledgments(self, cli_runner: CliRunner) -> None:
        """ack --list shows existing acknowledgments."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"
            # Create acknowledgment file
            acks_data = {
                "version": "1.0",
                "acknowledgments": [
                    {
                        "collision_key": "aunt-susan",
                        "node_label": "Aunt Susan",
                        "path": ["[SOCIAL] Aunt Susan", "DRAINS", "Drained"],
                        "timestamp": "2026-01-21T18:00:00Z",
                    }
                ],
            }
            acks_path.write_text(json.dumps(acks_data))

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
            ):
                result = cli_runner.invoke(main, ["ack", "--list"])

                assert result.exit_code == 0
                assert "aunt-susan" in result.output


class TestAckLifecycleIntegration:
    """Integration tests for full acknowledgment lifecycle."""

    def test_full_lifecycle_acknowledge_list_remove(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
    ) -> None:
        """Test full lifecycle: acknowledge → list → remove."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=sample_collisions,
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                # Step 1: Acknowledge collision
                result = cli_runner.invoke(main, ["ack", "aunt-susan"])
                assert result.exit_code == 0
                assert "Acknowledged" in result.output

                # Step 2: List shows acknowledgment
                result = cli_runner.invoke(main, ["ack", "--list"])
                assert result.exit_code == 0
                assert "aunt-susan" in result.output

                # Step 3: Remove acknowledgment
                result = cli_runner.invoke(main, ["ack", "aunt-susan", "--remove"])
                assert result.exit_code == 0
                assert "Removed" in result.output

                # Step 4: Verify list is now empty
                result = cli_runner.invoke(main, ["ack", "--list"])
                assert result.exit_code == 0
                assert "No acknowledgments" in result.output


class TestAckRemoveCommand:
    """Tests for ack --remove command."""

    def test_ack_remove_no_label(self, cli_runner: CliRunner) -> None:
        """ack --remove without label shows error."""
        result = cli_runner.invoke(main, ["ack", "--remove"])

        assert result.exit_code != 0
        assert "Label required" in result.output

    def test_ack_remove_existing(self, cli_runner: CliRunner) -> None:
        """ack --remove removes existing acknowledgment."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"
            # Create acknowledgment file
            acks_data = {
                "version": "1.0",
                "acknowledgments": [
                    {
                        "collision_key": "aunt-susan",
                        "node_label": "Aunt Susan",
                        "path": ["[SOCIAL] Aunt Susan", "DRAINS", "Drained"],
                        "timestamp": "2026-01-21T18:00:00Z",
                    }
                ],
            }
            acks_path.write_text(json.dumps(acks_data))

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
            ):
                result = cli_runner.invoke(main, ["ack", "aunt-susan", "--remove"])

                assert result.exit_code == 0
                assert "Removed" in result.output

                # Verify removal
                with open(acks_path) as f:
                    data = json.load(f)
                assert len(data["acknowledgments"]) == 0

    def test_ack_remove_not_found(self, cli_runner: CliRunner) -> None:
        """ack <label> --remove shows error when acknowledgment not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=Path(tmp_dir) / "acks.json",
                ),
            ):
                result = cli_runner.invoke(main, ["ack", "nonexistent", "--remove"])

                assert result.exit_code != 0
                assert "no acknowledgment found" in result.output.lower()

    def test_ack_remove_fuzzy_match(self, cli_runner: CliRunner) -> None:
        """ack --remove uses fuzzy matching for labels."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            acks_path = Path(tmp_dir) / "acks.json"
            # Create acknowledgment file with normalized key
            acks_data = {
                "version": "1.0",
                "acknowledgments": [
                    {
                        "collision_key": "aunt-susan",
                        "node_label": "Aunt Susan",
                        "path": ["[SOCIAL] Aunt Susan", "DRAINS", "Drained"],
                        "timestamp": "2026-01-21T18:00:00Z",
                    }
                ],
            }
            acks_path.write_text(json.dumps(acks_data))

            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=Path(tmp_dir),
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
            ):
                # Use space instead of dash - should fuzzy match
                result = cli_runner.invoke(main, ["ack", "Aunt Susan", "--remove"])

                assert result.exit_code == 0
                assert "Removed" in result.output

                # Verify removal
                with open(acks_path) as f:
                    data = json.load(f)
                assert len(data["acknowledgments"]) == 0
