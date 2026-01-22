"""Integration tests for configuration persistence.

Tests end-to-end config file operations using temp directories.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sentinel.cli.commands import main
from sentinel.core.config import (
    DEFAULT_CONFIG,
    get_config_path,
    get_xdg_config_home,
    load_config,
    write_default_config,
)
from sentinel.core.constants import EXIT_CONFIG_ERROR, EXIT_SUCCESS
from sentinel.core.types import Edge, Graph, Node


class TestConfigFilePermissions:
    """Integration tests for config file permissions (AC #6)."""

    def test_config_directory_has_700_permissions(self, tmp_path: Path) -> None:
        """Config directory is created with 700 permissions (owner only rwx)."""
        custom_xdg = str(tmp_path / "secure-config")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_dir = get_xdg_config_home()

        mode = config_dir.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected directory permissions 0o700, got {oct(mode)}"

    def test_config_file_has_600_permissions(self, tmp_path: Path) -> None:
        """Config file is created with 600 permissions (owner only rw)."""
        custom_xdg = str(tmp_path / "secure-config")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected file permissions 0o600, got {oct(mode)}"

    def test_permissions_on_nested_directory_creation(self, tmp_path: Path) -> None:
        """Directory permissions correct even when creating nested paths."""
        # Create a deeply nested XDG path that doesn't exist
        custom_xdg = str(tmp_path / "deep" / "nested" / "config")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_dir = get_xdg_config_home()

        mode = config_dir.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"


class TestConfigPersistenceRoundTrip:
    """Integration tests for config persistence round-trip."""

    def test_write_then_load_preserves_values(self, tmp_path: Path) -> None:
        """Write default config then load preserves all values."""
        custom_xdg = str(tmp_path)

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            # Write default config
            write_default_config()

            # Load it back
            loaded = load_config()

        # Should match defaults
        assert loaded.energy_threshold == DEFAULT_CONFIG.energy_threshold
        assert loaded.llm_provider == DEFAULT_CONFIG.llm_provider
        assert loaded.default_format == DEFAULT_CONFIG.default_format
        assert loaded.telemetry_enabled == DEFAULT_CONFIG.telemetry_enabled

    def test_modified_config_persists(self, tmp_path: Path) -> None:
        """Manually modified config values persist across loads."""
        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"

        # Write custom config
        config_file.write_text(
            'energy_threshold = "high"\ndefault_format = "html"\ntelemetry_enabled = true\n'
        )

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            loaded = load_config()

        assert loaded.energy_threshold == "high"
        assert loaded.default_format == "html"
        assert loaded.telemetry_enabled is True
        # Unspecified values should be defaults
        assert loaded.llm_provider == DEFAULT_CONFIG.llm_provider

    def test_partial_config_preserves_defaults(self, tmp_path: Path) -> None:
        """Partial config file uses defaults for missing fields."""
        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"

        # Only set one value
        config_file.write_text('energy_threshold = "low"\n')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            loaded = load_config()

        assert loaded.energy_threshold == "low", "Specified value should be used"
        assert loaded.llm_provider == DEFAULT_CONFIG.llm_provider
        assert loaded.llm_model == DEFAULT_CONFIG.llm_model
        assert loaded.default_format == DEFAULT_CONFIG.default_format
        assert loaded.telemetry_enabled == DEFAULT_CONFIG.telemetry_enabled


class TestConfigXdgCompliance:
    """Integration tests for XDG Base Directory Specification compliance."""

    def test_respects_xdg_config_home_environment_variable(self, tmp_path: Path) -> None:
        """XDG_CONFIG_HOME environment variable is respected."""
        custom_xdg = str(tmp_path / "custom-xdg-config")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        expected_path = Path(custom_xdg) / "sentinel" / "config.toml"
        assert config_path == expected_path
        assert config_path.exists()

    def test_uses_default_path_without_xdg_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls back to ~/.config/sentinel/ when XDG_CONFIG_HOME not set."""
        # Clear XDG_CONFIG_HOME
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        # Mock home to use tmp_path
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        config_path = get_config_path()

        expected_path = mock_home / ".config" / "sentinel" / "config.toml"
        assert config_path == expected_path


class TestConfigErrorHandling:
    """Integration tests for config error handling."""

    def test_missing_config_file_uses_defaults_silently(self, tmp_path: Path) -> None:
        """Missing config file returns defaults without error."""
        custom_xdg = str(tmp_path / "empty-config")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            # No config file exists
            loaded = load_config()

        assert loaded == DEFAULT_CONFIG

    def test_invalid_toml_raises_config_error(self, tmp_path: Path) -> None:
        """Invalid TOML syntax raises ConfigError."""
        from sentinel.core.exceptions import ConfigError

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("invalid = [unclosed bracket")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            with pytest.raises(ConfigError) as exc_info:
                load_config()

        assert "Configuration file is invalid" in str(exc_info.value)

    def test_unknown_keys_in_config_are_ignored(self, tmp_path: Path) -> None:
        """Unknown keys in config file are ignored gracefully."""
        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text(
            "# Valid key\n"
            'energy_threshold = "high"\n\n'
            "# Unknown keys (future-proofing)\n"
            "some_future_setting = true\n"
            'another_unknown = "value"\n'
        )

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            loaded = load_config()

        # Valid key should be used
        assert loaded.energy_threshold == "high"
        # Unknown keys should be ignored, defaults used for missing
        assert loaded.llm_provider == DEFAULT_CONFIG.llm_provider

    def test_invalid_literal_value_raises_config_error(self, tmp_path: Path) -> None:
        """Invalid Literal field values are rejected at load time."""
        from sentinel.core.exceptions import ConfigError

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "super_high"')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            with pytest.raises(ConfigError) as exc_info:
                load_config()

        assert "Invalid energy_threshold" in str(exc_info.value)
        assert "low" in str(exc_info.value)  # Lists valid options


class TestCustomPathPermissions:
    """Integration tests for custom path permission hardening (M2 fix)."""

    def test_custom_path_parent_gets_secure_permissions(self, tmp_path: Path) -> None:
        """Custom config path parent directory gets 700 permissions."""
        custom_config = tmp_path / "custom" / "nested" / "config.toml"

        write_default_config(custom_config)

        # Check parent directory permissions
        parent_mode = custom_config.parent.stat().st_mode & 0o777
        assert parent_mode == 0o700, f"Expected parent dir 0o700, got {oct(parent_mode)}"

    def test_custom_path_file_gets_secure_permissions(self, tmp_path: Path) -> None:
        """Custom config file gets 600 permissions."""
        custom_config = tmp_path / "custom" / "config.toml"

        write_default_config(custom_config)

        # Check file permissions
        file_mode = custom_config.stat().st_mode & 0o777
        assert file_mode == 0o600, f"Expected file 0o600, got {oct(file_mode)}"


def _create_threshold_test_graph(confidence: float = 0.6) -> Graph:
    """Create a graph with a collision at specified confidence for threshold testing.

    Pattern: (dinner)-[:DRAINS]->(drained)-[:CONFLICTS_WITH]->
             (focused)<-[:REQUIRES]-(presentation)
    """
    nodes = (
        Node(
            id="activity-dinner",
            label="dinner",
            type="Activity",
            source="user-stated",
            metadata={"domain": "social"},
        ),
        Node(
            id="energystate-drained",
            label="drained",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="energystate-focused",
            label="focused",
            type="EnergyState",
            source="ai-inferred",
            metadata={},
        ),
        Node(
            id="activity-presentation",
            label="presentation",
            type="Activity",
            source="user-stated",
            metadata={"domain": "professional"},
        ),
    )
    edges = (
        Edge(
            source_id="activity-dinner",
            target_id="energystate-drained",
            relationship="DRAINS",
            confidence=confidence,
            metadata={},
        ),
        Edge(
            source_id="energystate-drained",
            target_id="energystate-focused",
            relationship="CONFLICTS_WITH",
            confidence=confidence,
            metadata={},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="energystate-focused",
            relationship="REQUIRES",
            confidence=confidence,
            metadata={},
        ),
    )
    return Graph(nodes=nodes, edges=edges)


class TestCheckCommandThresholdIntegration:
    """Integration tests for check command using config threshold (Story 5.2)."""

    def test_check_command_uses_config_threshold_high(self, tmp_path: Path) -> None:
        """Check command respects 'high' threshold from config (AC #1).

        A collision at confidence 0.6 should be hidden when threshold is 'high' (0.7).
        """
        # Create config with "high" threshold
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\n')

        # Create graph with collision at 0.6 confidence (below high threshold)
        graph = _create_threshold_test_graph(confidence=0.6)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result = runner.invoke(main, ["check"])

        # Collision at 0.6 should be hidden with "high" (0.7) threshold
        # Should show success message or "no collisions" since all filtered out
        assert result.exit_code == EXIT_SUCCESS, f"Expected success, got {result.exit_code}"
        assert "collision" not in result.output.lower() or "no" in result.output.lower(), (
            f"Expected collision to be hidden with high threshold. Output: {result.output}"
        )

    def test_check_command_uses_config_threshold_low(self, tmp_path: Path) -> None:
        """Check command respects 'low' threshold from config (AC #3).

        A collision at confidence 0.35 should be shown when threshold is 'low' (0.3).
        """
        # Create config with "low" threshold
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "low"\n')

        # Create graph with collision at 0.35 confidence (above low threshold)
        graph = _create_threshold_test_graph(confidence=0.35)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result = runner.invoke(main, ["check"])

        # Collision at 0.35 should be visible with "low" (0.3) threshold
        # Should have non-zero exit code indicating collision detected
        assert "collision" in result.output.lower() or "risk" in result.output.lower(), (
            f"Expected collision visible with low threshold. Output: {result.output}"
        )

    def test_threshold_change_takes_effect_immediately(self, tmp_path: Path) -> None:
        """Config threshold change is applied on next run without restart (AC #6)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"

        # Create graph with collision at 0.6 confidence
        graph = _create_threshold_test_graph(confidence=0.6)

        runner = CliRunner()

        # First run with "high" threshold - collision should be hidden
        config_file.write_text('energy_threshold = "high"\n')
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result1 = runner.invoke(main, ["check"])

        assert result1.exit_code == EXIT_SUCCESS, "High threshold should hide 0.6 collision"

        # Second run with "medium" threshold - collision should be visible
        config_file.write_text('energy_threshold = "medium"\n')
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result2 = runner.invoke(main, ["check"])

        # With medium threshold (0.5), collision at 0.6 should be visible
        assert "collision" in result2.output.lower() or "risk" in result2.output.lower(), (
            f"Medium threshold should show 0.6 collision. Output: {result2.output}"
        )

    def test_invalid_threshold_raises_config_error_with_exit_code(self, tmp_path: Path) -> None:
        """Invalid threshold value causes EXIT_CONFIG_ERROR (AC #4)."""
        # Create config with invalid threshold
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "super_high"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"Expected EXIT_CONFIG_ERROR ({EXIT_CONFIG_ERROR}), got {result.exit_code}"
        )
        assert "Invalid energy_threshold" in result.output, (
            f"Expected error message about invalid threshold. Output: {result.output}"
        )
        assert "super_high" in result.output, (
            f"Expected invalid value in error message. Output: {result.output}"
        )

    def test_boundary_condition_high_threshold_exact_match(self, tmp_path: Path) -> None:
        """Collision at exactly 0.7 is shown with 'high' threshold (boundary test).

        Tests >= comparison: confidence 0.7 with threshold 0.7 should be shown.
        """
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\n')

        # Collision at exactly 0.7 (the high threshold boundary)
        graph = _create_threshold_test_graph(confidence=0.7)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result = runner.invoke(main, ["check"])

        # Collision at 0.7 should be visible with "high" (0.7) threshold (>= comparison)
        assert "collision" in result.output.lower() or "risk" in result.output.lower(), (
            f"Expected collision at boundary to be visible. Output: {result.output}"
        )

    def test_boundary_condition_low_threshold_exact_match(self, tmp_path: Path) -> None:
        """Collision at exactly 0.3 is shown with 'low' threshold (boundary test).

        Tests >= comparison: confidence 0.3 with threshold 0.3 should be shown.
        """
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "low"\n')

        # Collision at exactly 0.3 (the low threshold boundary)
        graph = _create_threshold_test_graph(confidence=0.3)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                mock_engine = mock_engine_class.return_value
                mock_engine.load.return_value = graph

                result = runner.invoke(main, ["check"])

        # Collision at 0.3 should be visible with "low" (0.3) threshold (>= comparison)
        assert "collision" in result.output.lower() or "risk" in result.output.lower(), (
            f"Expected collision at boundary to be visible. Output: {result.output}"
        )


class TestApiKeyValidationIntegration:
    """Integration tests for API key validation in CLI commands (Story 5.3)."""

    def test_paste_command_validates_api_key(self, tmp_path: Path) -> None:
        """Paste command exits with code 3 when no API key available."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}, clear=True):
            result = runner.invoke(main, ["paste"], input="Test schedule\n")

        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"Expected EXIT_CONFIG_ERROR ({EXIT_CONFIG_ERROR}), got {result.exit_code}"
        )
        assert "No API key found" in result.output or "API key" in result.output, (
            f"Expected API key error message. Output: {result.output}"
        )

    def test_openai_embeddings_without_api_key_shows_api_key_error(self, tmp_path: Path) -> None:
        """No LLM_API_KEY shows API key error (validate_api_key runs first)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('embedding_provider = "openai"\n')

        runner = CliRunner()
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": str(tmp_path / ".config")},
            clear=True,
        ):
            result = runner.invoke(main, ["paste"], input="Test schedule\n")

        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"Expected EXIT_CONFIG_ERROR ({EXIT_CONFIG_ERROR}), got {result.exit_code}"
        )
        # validate_api_key() runs before check_embedding_compatibility()
        assert "No API key found" in result.output, (
            f"Expected API key error message. Output: {result.output}"
        )
        assert "LLM_API_KEY" in result.output, (
            f"Expected LLM_API_KEY in error message. Output: {result.output}"
        )

    def test_paste_command_succeeds_with_valid_api_key(self, tmp_path: Path) -> None:
        """Paste command proceeds (to mocked ingest) with valid LLM_API_KEY."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)

        runner = CliRunner()
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": str(tmp_path / ".config"), "LLM_API_KEY": "sk-test-key"},
            clear=True,
        ):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                from unittest.mock import AsyncMock

                mock_engine = mock_engine_class.return_value
                # Mock ingest to return a Graph (use AsyncMock for coroutine)
                mock_graph = Graph(nodes=(), edges=())
                mock_engine.ingest = AsyncMock(return_value=mock_graph)
                mock_engine.persist.return_value = None

                result = runner.invoke(main, ["paste"], input="Test schedule\n")

        # Should not fail with API key error
        assert result.exit_code != EXIT_CONFIG_ERROR or "API key" not in result.output, (
            f"Should not fail with API key error. Output: {result.output}"
        )

    def test_ollama_embedding_bypasses_openai_key_check(self, tmp_path: Path) -> None:
        """Ollama embedding provider doesn't require OpenAI API key."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text(
            'llm_provider = "ollama"\n'
            'llm_endpoint = "http://localhost:11434/v1"\n'
            'embedding_provider = "ollama"\n'
            'embedding_model = "nomic-embed-text:latest"\n'
        )

        runner = CliRunner()
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": str(tmp_path / ".config"), "LLM_API_KEY": "ollama-key"},
            clear=True,
        ):
            with patch("sentinel.core.engine.CogneeEngine") as mock_engine_class:
                from unittest.mock import AsyncMock

                mock_engine = mock_engine_class.return_value
                mock_graph = Graph(nodes=(), edges=())
                mock_engine.ingest = AsyncMock(return_value=mock_graph)
                mock_engine.persist.return_value = None

                result = runner.invoke(main, ["paste"], input="Test schedule\n")

        # Should not fail with OpenAI API key error
        assert "OpenAI API key" not in result.output, (
            f"Should not require OpenAI key with Ollama. Output: {result.output}"
        )

    def test_check_command_validates_api_key(self, tmp_path: Path) -> None:
        """Check command exits with code 3 when no API key available (AC6)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}, clear=True):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"Expected EXIT_CONFIG_ERROR ({EXIT_CONFIG_ERROR}), got {result.exit_code}"
        )
        assert "No API key found" in result.output or "API key" in result.output, (
            f"Expected API key error message. Output: {result.output}"
        )

    def test_check_command_validates_api_key_before_embedding(self, tmp_path: Path) -> None:
        """Check command validates API key before embedding compatibility (AC6)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('embedding_provider = "openai"\n')

        runner = CliRunner()
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": str(tmp_path / ".config")},
            clear=True,
        ):
            result = runner.invoke(main, ["check"])

        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"Expected EXIT_CONFIG_ERROR ({EXIT_CONFIG_ERROR}), got {result.exit_code}"
        )
        # validate_api_key() runs before check_embedding_compatibility()
        assert "No API key found" in result.output, (
            f"Expected API key error message. Output: {result.output}"
        )


class TestConfigCommandIntegration:
    """Integration tests for config CLI command (Story 5.4)."""

    def test_config_no_args_shows_all_settings(self, tmp_path: Path) -> None:
        """sentinel config shows all settings formatted (AC1)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\nllm_provider = "anthropic"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert "high" in result.output, "Should show energy_threshold value"
        assert "anthropic" in result.output, "Should show llm_provider value"
        assert "LLM" in result.output, "Should have section headers"

    def test_config_single_arg_shows_value(self, tmp_path: Path) -> None:
        """sentinel config energy_threshold shows 'high' (AC2)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "energy_threshold"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert result.output.strip() == "high", f"Expected 'high', got: {result.output}"

    def test_config_two_args_updates_file(self, tmp_path: Path) -> None:
        """sentinel config energy_threshold high updates config.toml (AC3)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "medium"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "energy_threshold", "high"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert "Set energy_threshold = high" in result.output, (
            f"Expected confirmation. Output: {result.output}"
        )

        # Verify file was updated
        loaded = load_config(config_file)
        assert loaded.energy_threshold == "high"

    def test_config_reset_restores_defaults(self, tmp_path: Path) -> None:
        """sentinel config --reset restores DEFAULT_CONFIG_TOML (AC4)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\nllm_provider = "anthropic"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "--reset"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert "reset to defaults" in result.output.lower(), (
            f"Expected confirmation. Output: {result.output}"
        )

        # Verify file was reset
        loaded = load_config(config_file)
        assert loaded.energy_threshold == DEFAULT_CONFIG.energy_threshold
        assert loaded.llm_provider == DEFAULT_CONFIG.llm_provider

    def test_config_invalid_key_shows_error_and_valid_keys(self, tmp_path: Path) -> None:
        """sentinel config invalid_key shows error with valid key list (AC2)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "invalid_key"])

        from sentinel.core.constants import EXIT_USER_ERROR

        assert result.exit_code == EXIT_USER_ERROR, f"Expected error. Output: {result.output}"
        assert "Unknown configuration key" in result.output, (
            f"Expected error message. Output: {result.output}"
        )
        assert "invalid_key" in result.output, f"Expected key in error. Output: {result.output}"

    def test_config_invalid_value_shows_error_and_valid_values(self, tmp_path: Path) -> None:
        """sentinel config energy_threshold bad shows error with valid values (AC3)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "medium"\n')

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "energy_threshold", "extreme"])

        from sentinel.core.constants import EXIT_USER_ERROR

        assert result.exit_code == EXIT_USER_ERROR, f"Expected error. Output: {result.output}"
        assert "Invalid value" in result.output, f"Expected error. Output: {result.output}"
        assert "extreme" in result.output, f"Expected value in error. Output: {result.output}"
        # Should show valid values
        assert "low" in result.output or "medium" in result.output or "high" in result.output, (
            f"Expected valid values listed. Output: {result.output}"
        )

    def test_config_ollama_multi_command_setup(self, tmp_path: Path) -> None:
        """Full Ollama setup via multiple config commands works (AC6)."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        write_default_config(config_file)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            # Run multiple config commands to set up Ollama
            result1 = runner.invoke(main, ["config", "llm_provider", "ollama"])
            result2 = runner.invoke(main, ["config", "llm_model", "llama3.1:8b"])
            result3 = runner.invoke(main, ["config", "llm_endpoint", "http://localhost:11434/v1"])
            result4 = runner.invoke(main, ["config", "embedding_provider", "ollama"])
            result5 = runner.invoke(main, ["config", "embedding_model", "nomic-embed-text:latest"])

        # All commands should succeed
        assert result1.exit_code == EXIT_SUCCESS, f"llm_provider failed: {result1.output}"
        assert result2.exit_code == EXIT_SUCCESS, f"llm_model failed: {result2.output}"
        assert result3.exit_code == EXIT_SUCCESS, f"llm_endpoint failed: {result3.output}"
        assert result4.exit_code == EXIT_SUCCESS, f"embedding_provider failed: {result4.output}"
        assert result5.exit_code == EXIT_SUCCESS, f"embedding_model failed: {result5.output}"

        # Verify final config
        loaded = load_config(config_file)
        assert loaded.llm_provider == "ollama"
        assert loaded.llm_model == "llama3.1:8b"
        assert loaded.llm_endpoint == "http://localhost:11434/v1"
        assert loaded.embedding_provider == "ollama"
        assert loaded.embedding_model == "nomic-embed-text:latest"

    def test_config_help_lists_all_keys(self) -> None:
        """sentinel config --help lists all valid keys with descriptions (AC5)."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--help"])

        assert result.exit_code == EXIT_SUCCESS, f"Help failed: {result.output}"
        assert "energy_threshold" in result.output
        assert "llm_provider" in result.output
        assert "llm_model" in result.output
        assert "embedding_provider" in result.output
        assert "telemetry_enabled" in result.output

    def test_config_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Config command creates config file if it doesn't exist."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        assert not config_file.exists()

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "energy_threshold", "high"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert config_file.exists(), "Config file should be created"

        loaded = load_config(config_file)
        assert loaded.energy_threshold == "high"

    def test_config_telemetry_boolean_conversion(self, tmp_path: Path) -> None:
        """Config command converts telemetry_enabled string to boolean."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("telemetry_enabled = false\n")

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "telemetry_enabled", "true"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"

        loaded = load_config(config_file)
        assert loaded.telemetry_enabled is True

    def test_config_displays_endpoint_not_set(self, tmp_path: Path) -> None:
        """Config command shows (not set) for empty llm_endpoint."""
        config_dir = tmp_path / ".config" / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        write_default_config(config_file)

        runner = CliRunner()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = runner.invoke(main, ["config", "llm_endpoint"])

        assert result.exit_code == EXIT_SUCCESS, f"Expected success. Output: {result.output}"
        assert "(not set)" in result.output, f"Expected (not set). Output: {result.output}"
