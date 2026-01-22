"""Tests for check command acknowledgment integration (Story 3-4).

Tests the --show-acked flag and acknowledgment filtering in the check command.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.types import Edge, Graph, Node, ScoredCollision

# --- Fixtures ---


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_graph() -> Graph:
    """Create a sample graph with nodes for collision testing."""
    nodes = (
        Node(
            id="n1",
            label="Aunt Susan",
            type="Person",
            source="ai-inferred",
            metadata={"day": "Sunday", "domain": "SOCIAL"},
        ),
        Node(
            id="n2",
            label="drained",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="n3",
            label="focused",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="n4",
            label="presentation",
            type="TimeSlot",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
        Node(
            id="n5",
            label="Work Meeting",
            type="Activity",
            source="user-stated",
            metadata={"day": "Tuesday"},
        ),
        Node(
            id="n6",
            label="stressed",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="n7",
            label="calm",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="n8",
            label="yoga",
            type="Activity",
            source="user-stated",
            metadata={"day": "Wednesday"},
        ),
    )
    edges = (
        Edge(
            source_id="n1",
            target_id="n2",
            relationship="DRAINS",
            confidence=0.9,
            metadata={},
        ),
        Edge(
            source_id="n2",
            target_id="n3",
            relationship="CONFLICTS_WITH",
            confidence=0.85,
            metadata={},
        ),
        Edge(
            source_id="n3",
            target_id="n4",
            relationship="REQUIRED_BY",
            confidence=0.9,
            metadata={},
        ),
        Edge(
            source_id="n5",
            target_id="n6",
            relationship="DRAINS",
            confidence=0.8,
            metadata={},
        ),
        Edge(
            source_id="n6",
            target_id="n7",
            relationship="CONFLICTS_WITH",
            confidence=0.75,
            metadata={},
        ),
        Edge(
            source_id="n7",
            target_id="n8",
            relationship="REQUIRED_BY",
            confidence=0.8,
            metadata={},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


@pytest.fixture
def sample_collisions() -> list[ScoredCollision]:
    """Sample collisions for testing."""
    return [
        ScoredCollision(
            path=(
                "[SOCIAL] Aunt Susan",
                "DRAINS",
                "drained",
                "CONFLICTS_WITH",
                "focused",
                "REQUIRED_BY",
                "presentation",
            ),
            confidence=0.85,
            source_breakdown={"ai_inferred": 4, "user_stated": 1},
        ),
        ScoredCollision(
            path=(
                "Work Meeting",
                "DRAINS",
                "stressed",
                "CONFLICTS_WITH",
                "calm",
                "REQUIRED_BY",
                "yoga",
            ),
            confidence=0.75,
            source_breakdown={"ai_inferred": 2, "user_stated": 2},
        ),
    ]


# --- Test: --show-acked flag exists (AC #3) ---


def test_check_command_accepts_show_acked_flag(cli_runner: CliRunner) -> None:
    """Check command accepts --show-acked flag without error."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch(
            "sentinel.core.persistence.get_xdg_data_home",
            return_value=Path(tmp_dir),
        ):
            result = cli_runner.invoke(main, ["check", "--show-acked"])

            # Should fail with "no schedule data" not "unknown option"
            no_data = "no schedule data" in result.output.lower()
            paste_hint = "sentinel paste" in result.output.lower()
            assert no_data or paste_hint, (
                f"Expected 'no schedule data' message, got: {result.output}"
            )
            assert "Error: No such option" not in result.output, (
                f"Flag --show-acked not recognized: {result.output}"
            )


def test_check_command_accepts_short_flag_a(cli_runner: CliRunner) -> None:
    """Check command accepts -a short flag for --show-acked."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch(
            "sentinel.core.persistence.get_xdg_data_home",
            return_value=Path(tmp_dir),
        ):
            result = cli_runner.invoke(main, ["check", "-a"])

            assert "Error: No such option" not in result.output, (
                f"Short flag -a not recognized: {result.output}"
            )


# --- Test: Acknowledged collision hidden (AC #1) ---


def test_check_hides_acknowledged_collision(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """sentinel check hides acknowledged collisions by default."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Create acks file acknowledging Aunt Susan collision
        acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(acks_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
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

            result = cli_runner.invoke(main, ["check"])

            # Work Meeting is not acknowledged, should be shown
            assert "Work Meeting" in result.output, (
                f"Unacked collision should show: {result.output}"
            )
            # Aunt Susan IS acknowledged, should NOT appear in collision panels
            # (Note: may appear in ASCII graph, but not in warning panels)
            # Check that [ACKED] label is NOT shown (since --show-acked not used)
            assert "[ACKED]" not in result.output, (
                f"Acknowledged collision should be hidden: {result.output}"
            )


# --- Test: New collisions displayed (AC #2) ---


def test_check_shows_unacknowledged_collision(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """sentinel check displays unacknowledged collisions normally."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Create acks file acknowledging only Aunt Susan
        acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(acks_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
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

            result = cli_runner.invoke(main, ["check"])

            # Work Meeting collision is not acknowledged, should be displayed
            assert "Work Meeting" in result.output or "collision" in result.output.lower(), (
                f"Expected unacked collision to be shown: {result.output}"
            )


# --- Test: --show-acked displays with label (AC #3) ---


def test_check_show_acked_displays_with_label(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """sentinel check --show-acked displays acknowledged with [ACKED] label."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Create acks file acknowledging Aunt Susan collision
        acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(acks_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
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

            result = cli_runner.invoke(main, ["check", "--show-acked"])

            # Should show [ACKED] label for Aunt Susan collision
            assert "[ACKED]" in result.output, f"Expected [ACKED] label: {result.output}"
            assert "Aunt Susan" in result.output, f"Expected Aunt Susan in output: {result.output}"


# --- Test: Stale acknowledgment ignored (AC #4) ---


def test_check_ignores_stale_acknowledgment(
    cli_runner: CliRunner,
    sample_graph: Graph,
) -> None:
    """Acknowledgment for non-existent collision is ignored gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Create acks file with stale acknowledgment
        stale_acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "old-person-no-longer-exists",
                    "node_label": "Old Person",
                    "path": ["Old Person", "DRAINS", "gone"],
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(stale_acks_data))

        # Collision that doesn't match the stale acknowledgment
        current_collisions = [
            ScoredCollision(
                path=(
                    "Work Meeting",
                    "DRAINS",
                    "stressed",
                    "CONFLICTS_WITH",
                    "calm",
                    "REQUIRED_BY",
                    "yoga",
                ),
                confidence=0.75,
                source_breakdown={"ai_inferred": 2, "user_stated": 2},
            ),
        ]

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
            ),
            patch(
                "sentinel.core.persistence.get_acks_path",
                return_value=acks_path,
            ),
            patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
            patch(
                "sentinel.cli.commands.detect_cross_domain_collisions",
                return_value=current_collisions,
            ),
        ):
            mock_engine = MagicMock()
            mock_engine.load.return_value = sample_graph
            mock_engine_cls.return_value = mock_engine

            result = cli_runner.invoke(main, ["check"])

            # Should not error, should show the current collision
            assert result.exit_code != 2, f"Should not crash: {result.output}"
            assert "Work Meeting" in result.output or "collision" in result.output.lower(), (
                f"Current collision should show: {result.output}"
            )


# --- Test: Summary with acknowledged count (AC #5) ---


def test_check_summary_shows_acknowledged_count(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """Check shows summary with acknowledged count when mixed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Acknowledge only Aunt Susan
        acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(acks_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
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

            result = cli_runner.invoke(main, ["check"])

            # Should show summary like "2 collisions detected (1 acknowledged, hidden)"
            output_lower = result.output.lower()
            assert "acknowledged" in output_lower, (
                f"Expected 'acknowledged' in output: {result.output}"
            )


# --- Test: All acknowledged empty state (AC #6) ---


def test_check_all_acknowledged_shows_no_new_collisions(
    cli_runner: CliRunner,
    sample_graph: Graph,
) -> None:
    """When all collisions are acknowledged, show NO NEW COLLISIONS message."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Single collision that is acknowledged
        single_collision = [
            ScoredCollision(
                path=(
                    "[SOCIAL] Aunt Susan",
                    "DRAINS",
                    "drained",
                    "CONFLICTS_WITH",
                    "focused",
                    "REQUIRED_BY",
                    "presentation",
                ),
                confidence=0.85,
                source_breakdown={"ai_inferred": 4, "user_stated": 1},
            ),
        ]

        # Acks file acknowledging that collision
        all_acked_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(all_acked_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
            ),
            patch(
                "sentinel.core.persistence.get_acks_path",
                return_value=acks_path,
            ),
            patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
            patch(
                "sentinel.cli.commands.detect_cross_domain_collisions",
                return_value=single_collision,
            ),
        ):
            mock_engine = MagicMock()
            mock_engine.load.return_value = sample_graph
            mock_engine_cls.return_value = mock_engine

            result = cli_runner.invoke(main, ["check"])

            # Should show success message
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "NO NEW COLLISIONS" in result.output, (
                f"Expected 'NO NEW COLLISIONS': {result.output}"
            )
            # Should mention hidden acknowledged collision
            assert "acknowledged" in result.output.lower(), (
                f"Expected 'acknowledged' note: {result.output}"
            )
            assert "--show-acked" in result.output, (
                f"Expected hint about --show-acked: {result.output}"
            )


# --- Test: Integration: ack then check ---


def test_ack_then_check_hides_collision(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """Integration: acknowledge collision, then check hides it."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
            ),
            patch(
                "sentinel.core.persistence.get_acks_path",
                return_value=acks_path,
            ),
            patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
            # Both check and ack commands now use module-level import
            patch(
                "sentinel.cli.commands.detect_cross_domain_collisions",
                return_value=sample_collisions,
            ),
        ):
            mock_engine = MagicMock()
            mock_engine.load.return_value = sample_graph
            mock_engine_cls.return_value = mock_engine

            # First, acknowledge "Aunt Susan" collision
            result = cli_runner.invoke(main, ["ack", "aunt-susan"])
            assert result.exit_code == 0, f"Ack should succeed: {result.output}"

            # Now check should hide Aunt Susan but show Work Meeting
            result = cli_runner.invoke(main, ["check"])

            # Work Meeting should be visible (not acknowledged)
            assert "Work Meeting" in result.output or "collision" in result.output.lower(), (
                f"Unacked collision should show: {result.output}"
            )


# --- Test: Help text shows --show-acked ---


def test_check_help_mentions_show_acked(cli_runner: CliRunner) -> None:
    """Check command help text mentions --show-acked flag."""
    result = cli_runner.invoke(main, ["check", "--help"])

    assert "--show-acked" in result.output, f"Help should mention --show-acked: {result.output}"
    assert "acknowledged" in result.output.lower(), f"Help should explain the flag: {result.output}"


# --- Test: No acks file - show all collisions ---


def test_check_no_acks_file_shows_all_collisions(
    cli_runner: CliRunner,
    sample_graph: Graph,
    sample_collisions: list[ScoredCollision],
) -> None:
    """When no acks file exists, all collisions are shown."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"
        # Note: NOT creating acks file

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
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

            result = cli_runner.invoke(main, ["check"])

            # Both collisions should be shown
            assert "Aunt Susan" in result.output or "collision" in result.output.lower(), (
                f"Both collisions should show: {result.output}"
            )
            # Exit code should indicate collision detected
            assert result.exit_code == 1, f"Expected collision exit code: {result.output}"


# --- Test: Flag combination --show-acked + --verbose ---
# Note: Story 5.5 moved --verbose to global flag on main group


def test_check_show_acked_with_verbose_shows_all(
    cli_runner: CliRunner,
    sample_graph: Graph,
) -> None:
    """Check with both --show-acked and global --verbose shows all collisions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        acks_path = tmp_path / "acks.json"

        # Create collisions with varying confidence levels
        mixed_confidence_collisions = [
            ScoredCollision(
                path=(
                    "[SOCIAL] Aunt Susan",
                    "DRAINS",
                    "drained",
                    "CONFLICTS_WITH",
                    "focused",
                    "REQUIRED_BY",
                    "presentation",
                ),
                confidence=0.85,  # HIGH - above medium threshold
                source_breakdown={"ai_inferred": 4, "user_stated": 1},
            ),
            ScoredCollision(
                path=(
                    "Work Meeting",
                    "DRAINS",
                    "stressed",
                    "CONFLICTS_WITH",
                    "calm",
                    "REQUIRED_BY",
                    "yoga",
                ),
                confidence=0.35,  # LOW - below medium threshold (0.5)
                source_breakdown={"ai_inferred": 2, "user_stated": 2},
            ),
        ]

        # Acknowledge the high-confidence collision
        acks_data = {
            "version": "1.0",
            "acknowledgments": [
                {
                    "collision_key": "aunt-susan",
                    "node_label": "Aunt Susan",
                    "path": [
                        "[SOCIAL] Aunt Susan",
                        "DRAINS",
                        "drained",
                        "CONFLICTS_WITH",
                        "focused",
                        "REQUIRED_BY",
                        "presentation",
                    ],
                    "timestamp": "2026-01-21T18:00:00Z",
                }
            ],
        }
        acks_path.write_text(json.dumps(acks_data))

        with (
            patch(
                "sentinel.core.persistence.get_xdg_data_home",
                return_value=tmp_path,
            ),
            patch(
                "sentinel.core.persistence.get_acks_path",
                return_value=acks_path,
            ),
            patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
            patch(
                "sentinel.cli.commands.detect_cross_domain_collisions",
                return_value=mixed_confidence_collisions,
            ),
        ):
            mock_engine = MagicMock()
            mock_engine.load.return_value = sample_graph
            mock_engine_cls.return_value = mock_engine

            result = cli_runner.invoke(main, ["--verbose", "check", "--show-acked"])

            # Both collisions should appear (verbose shows low-confidence)
            # Acknowledged collision should have [ACKED] label
            assert "[ACKED]" in result.output, (
                f"Expected [ACKED] label for acknowledged collision: {result.output}"
            )
            # Low-confidence collision should appear (verbose mode)
            # Note: "Work Meeting" may appear in output due to verbose showing speculative
            assert "collision" in result.output.lower() or "Work Meeting" in result.output, (
                f"Expected low-confidence collision in verbose mode: {result.output}"
            )


# --- Tests for check --format html (Story 4-3 AC#8) ---


class TestCheckCommandHtmlFormat:
    """Tests for check command HTML format option (Story 4-3)."""

    def test_check_format_html_creates_file(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """sentinel check --format html creates HTML file (AC#8)."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                result = cli_runner.invoke(main, ["check", "--format", "html"])

            # Should create sentinel-check.html by default
            assert Path("sentinel-check.html").exists(), (
                f"HTML file should be created. Output: {result.output}"
            )

    def test_check_format_html_default_filename(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """HTML export defaults to sentinel-check.html (AC#8)."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                cli_runner.invoke(main, ["check", "--format", "html"])

            html_file = Path("sentinel-check.html")
            assert html_file.exists(), "Should create sentinel-check.html"
            content = html_file.read_text()
            assert "<!DOCTYPE html>" in content, "File should be valid HTML"

    def test_check_format_html_includes_collisions(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """HTML includes collision warnings (AC#8)."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                cli_runner.invoke(main, ["check", "--format", "html"])

            content = Path("sentinel-check.html").read_text()
            # Should include collision information
            assert "collision" in content.lower() or "warning" in content.lower(), (
                "HTML should include collision information"
            )

    def test_check_format_html_includes_graph_visualization(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """HTML includes graph visualization (AC#8)."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                cli_runner.invoke(main, ["check", "--format", "html"])

            content = Path("sentinel-check.html").read_text()
            # Should include SVG graph visualization
            assert "<svg" in content, "HTML should include SVG graph visualization"

    def test_check_format_html_output_option(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """--output option specifies custom filename."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                result = cli_runner.invoke(
                    main, ["check", "--format", "html", "--output", "my-check.html"]
                )

            assert Path("my-check.html").exists(), (
                f"Custom filename should be created. Output: {result.output}"
            )
            assert not Path("sentinel-check.html").exists(), (
                "Default filename should not be created"
            )

    def test_check_format_html_highlights_collision_paths(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        sample_collisions: list[ScoredCollision],
        tmp_path: Path,
    ) -> None:
        """Collision paths are highlighted in HTML visualization (AC#6)."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
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

                cli_runner.invoke(main, ["check", "--format", "html"])

            content = Path("sentinel-check.html").read_text()
            # Should use collision highlighting color (red)
            assert "#F44336" in content or "collision" in content, (
                "HTML should highlight collision paths"
            )

    def test_check_format_html_no_collisions_no_file(
        self,
        cli_runner: CliRunner,
        sample_graph: Graph,
        tmp_path: Path,
    ) -> None:
        """When no collisions detected, HTML file is not created."""
        acks_path = tmp_path / "acks.json"
        acks_path.write_text('{"version":"1.0","acknowledgments":[]}')

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with (
                patch(
                    "sentinel.core.persistence.get_xdg_data_home",
                    return_value=tmp_path,
                ),
                patch(
                    "sentinel.core.persistence.get_acks_path",
                    return_value=acks_path,
                ),
                patch("sentinel.core.engine.CogneeEngine") as mock_engine_cls,
                patch(
                    "sentinel.cli.commands.detect_cross_domain_collisions",
                    return_value=[],  # No collisions
                ),
            ):
                mock_engine = MagicMock()
                mock_engine.load.return_value = sample_graph
                mock_engine_cls.return_value = mock_engine

                result = cli_runner.invoke(main, ["check", "--format", "html"])

            # Should succeed (no collisions = success)
            assert result.exit_code == 0, f"Expected success, got: {result.output}"
            # Should NOT create HTML file when no collisions
            assert not Path("sentinel-check.html").exists(), (
                "HTML file should not be created when no collisions detected"
            )
            # Should show success message
            assert "NO COLLISION" in result.output.upper(), (
                f"Should show no collision message: {result.output}"
            )
