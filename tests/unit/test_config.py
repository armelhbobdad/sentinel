"""Unit tests for configuration utilities.

Tests XDG config path handling, config loading, and error handling.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetXdgConfigHome:
    """Tests for get_xdg_config_home() function."""

    def test_default_path_without_xdg_env(self) -> None:
        """Returns ~/.config/sentinel/ when XDG_CONFIG_HOME not set."""
        from sentinel.core.config import get_xdg_config_home

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = get_xdg_config_home()

        expected = Path.home() / ".config" / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_respects_xdg_config_home_env(self, tmp_path: Path) -> None:
        """Uses XDG_CONFIG_HOME environment variable when set."""
        from sentinel.core.config import get_xdg_config_home

        custom_xdg = str(tmp_path / "custom-config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = get_xdg_config_home()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"


class TestEnsureConfigDirectory:
    """Tests for ensure_config_directory() function."""

    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Creates config directory with mkdir -p behavior."""
        from sentinel.core.config import ensure_config_directory

        custom_xdg = str(tmp_path / "new-xdg-config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = ensure_config_directory()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"
        assert result.exists(), "Directory should exist"
        assert result.is_dir(), "Should be a directory"

    def test_sets_directory_permissions_700(self, tmp_path: Path) -> None:
        """Sets directory permissions to 700 (owner only)."""
        from sentinel.core.config import ensure_config_directory

        custom_xdg = str(tmp_path / "secure-xdg-config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = ensure_config_directory()

        # Check permissions (700 = rwx------)
        mode = result.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_idempotent_when_directory_exists(self, tmp_path: Path) -> None:
        """Returns existing directory without error."""
        from sentinel.core.config import ensure_config_directory

        custom_xdg = str(tmp_path / "existing-xdg-config")
        sentinel_dir = Path(custom_xdg) / "sentinel"
        sentinel_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = ensure_config_directory()

        assert result == sentinel_dir, f"Expected {sentinel_dir}, got {result}"
        assert result.exists(), "Directory should still exist"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates all parent directories (mkdir -p behavior)."""
        from sentinel.core.config import ensure_config_directory

        custom_xdg = str(tmp_path / "deep" / "nested" / "config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = ensure_config_directory()

        expected = Path(custom_xdg) / "sentinel"
        assert result == expected, f"Expected {expected}, got {result}"
        assert result.exists(), "Directory should exist"


class TestGetConfigPath:
    """Tests for get_config_path() function."""

    def test_returns_config_toml_in_config_home(self) -> None:
        """Returns {config_home}/config.toml path."""
        from sentinel.core.config import get_config_path, get_xdg_config_home

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = get_config_path()

        expected = get_xdg_config_home() / "config.toml"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_uses_custom_xdg_config_home(self, tmp_path: Path) -> None:
        """Uses custom XDG_CONFIG_HOME for config.toml path."""
        from sentinel.core.config import get_config_path

        custom_xdg = str(tmp_path / "custom-config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = get_config_path()

        expected = Path(custom_xdg) / "sentinel" / "config.toml"
        assert result == expected, f"Expected {expected}, got {result}"


class TestSentinelConfig:
    """Tests for SentinelConfig dataclass."""

    def test_config_is_frozen_dataclass(self) -> None:
        """SentinelConfig is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        from sentinel.core.config import SentinelConfig

        config = SentinelConfig()
        with pytest.raises(FrozenInstanceError):
            config.energy_threshold = "high"  # type: ignore[misc]

    def test_config_has_sensible_defaults(self) -> None:
        """SentinelConfig has sensible default values."""
        from sentinel.core.config import SentinelConfig

        config = SentinelConfig()
        assert config.energy_threshold == "medium", "Default energy threshold should be medium"
        assert config.llm_provider == "openai", "Default LLM provider should be openai"
        assert config.default_format == "text", "Default output format should be text"
        assert config.telemetry_enabled is False, "Telemetry should be disabled by default"

    def test_default_config_constant_exists(self) -> None:
        """DEFAULT_CONFIG constant provides default configuration."""
        from sentinel.core.config import DEFAULT_CONFIG, SentinelConfig

        assert isinstance(DEFAULT_CONFIG, SentinelConfig), "DEFAULT_CONFIG should be SentinelConfig"
        assert DEFAULT_CONFIG.energy_threshold == "medium", (
            "DEFAULT_CONFIG should have medium threshold"
        )

    def test_config_can_be_created_with_custom_values(self) -> None:
        """SentinelConfig accepts custom values."""
        from sentinel.core.config import SentinelConfig

        config = SentinelConfig(
            energy_threshold="high",
            llm_provider="anthropic",
            default_format="html",
            telemetry_enabled=True,
        )
        assert config.energy_threshold == "high"
        assert config.llm_provider == "anthropic"
        assert config.default_format == "html"
        assert config.telemetry_enabled is True


class TestConfigError:
    """Tests for ConfigError exception."""

    def test_config_error_inherits_from_sentinel_error(self) -> None:
        """ConfigError inherits from SentinelError."""
        from sentinel.core.exceptions import ConfigError, SentinelError

        assert issubclass(ConfigError, SentinelError), (
            "ConfigError should inherit from SentinelError"
        )
        err = ConfigError("test error")
        assert isinstance(err, SentinelError), "ConfigError instance should be SentinelError"

    def test_config_error_preserves_message(self) -> None:
        """ConfigError preserves the error message."""
        from sentinel.core.exceptions import ConfigError

        message = "Configuration file is invalid: unexpected key"
        err = ConfigError(message)
        assert str(err) == message, f"Expected '{message}', got '{err}'"


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_returns_default_config_when_file_missing(self, tmp_path: Path) -> None:
        """Returns DEFAULT_CONFIG when config file doesn't exist."""
        from sentinel.core.config import DEFAULT_CONFIG, load_config

        custom_xdg = str(tmp_path / "no-config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = load_config()

        assert result == DEFAULT_CONFIG, f"Expected default config, got {result}"

    def test_loads_valid_toml_config(self, tmp_path: Path) -> None:
        """Loads and parses valid TOML configuration."""
        from sentinel.core.config import load_config

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "high"\ntelemetry_enabled = true\n')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = load_config()

        assert result.energy_threshold == "high", f"Expected 'high', got {result.energy_threshold}"
        assert result.telemetry_enabled is True, f"Expected True, got {result.telemetry_enabled}"

    def test_merges_partial_config_with_defaults(self, tmp_path: Path) -> None:
        """Partial config file merges with defaults."""
        from sentinel.core.config import load_config

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        # Only specify energy_threshold, other values should come from defaults
        config_file.write_text('energy_threshold = "low"\n')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            result = load_config()

        assert result.energy_threshold == "low", "Specified value should be used"
        assert result.llm_provider == "openai", "Default should be used for unspecified fields"
        assert result.default_format == "text", "Default should be used for unspecified fields"

    def test_raises_config_error_on_invalid_toml(self, tmp_path: Path) -> None:
        """Raises ConfigError with parse details on invalid TOML."""
        from sentinel.core.config import load_config
        from sentinel.core.exceptions import ConfigError

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("invalid = [unclosed")

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            with pytest.raises(ConfigError) as exc_info:
                load_config()

        assert "Configuration file is invalid" in str(exc_info.value), (
            f"Expected parse error message, got: {exc_info.value}"
        )

    def test_raises_config_error_on_invalid_energy_threshold(self, tmp_path: Path) -> None:
        """Raises ConfigError when energy_threshold has invalid value."""
        from sentinel.core.config import load_config
        from sentinel.core.exceptions import ConfigError

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('energy_threshold = "invalid_value"')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            with pytest.raises(ConfigError) as exc_info:
                load_config()

        assert "Invalid energy_threshold" in str(exc_info.value)
        assert "invalid_value" in str(exc_info.value)

    def test_raises_config_error_on_invalid_default_format(self, tmp_path: Path) -> None:
        """Raises ConfigError when default_format has invalid value."""
        from sentinel.core.config import load_config
        from sentinel.core.exceptions import ConfigError

        custom_xdg = str(tmp_path)
        config_dir = tmp_path / "sentinel"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('default_format = "pdf"')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            with pytest.raises(ConfigError) as exc_info:
                load_config()

        assert "Invalid default_format" in str(exc_info.value)
        assert "pdf" in str(exc_info.value)

    def test_accepts_custom_config_path(self, tmp_path: Path) -> None:
        """Accepts custom config path argument."""
        from sentinel.core.config import load_config

        config_file = tmp_path / "custom-config.toml"
        config_file.write_text('default_format = "html"\n')

        result = load_config(config_file)

        assert result.default_format == "html", f"Expected 'html', got {result.default_format}"

    def test_returns_default_when_custom_path_missing(self, tmp_path: Path) -> None:
        """Returns DEFAULT_CONFIG when custom path doesn't exist."""
        from sentinel.core.config import DEFAULT_CONFIG, load_config

        nonexistent_path = tmp_path / "nonexistent.toml"
        result = load_config(nonexistent_path)

        assert result == DEFAULT_CONFIG, f"Expected default config, got {result}"

    def test_empty_config_file_uses_defaults(self, tmp_path: Path) -> None:
        """Empty config.toml file returns DEFAULT_CONFIG."""
        from sentinel.core.config import DEFAULT_CONFIG, load_config

        config_file = tmp_path / "empty-config.toml"
        config_file.write_text("")  # Empty file

        result = load_config(config_file)

        assert result == DEFAULT_CONFIG, f"Expected default config for empty file, got {result}"


class TestWriteDefaultConfig:
    """Tests for write_default_config() function."""

    def test_creates_config_file(self, tmp_path: Path) -> None:
        """Creates config.toml file in config directory."""
        from sentinel.core.config import get_config_path, write_default_config

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        assert config_path.exists(), "Config file should be created"

    def test_sets_file_permissions_600(self, tmp_path: Path) -> None:
        """Sets file permissions to 600 (owner read/write only)."""
        from sentinel.core.config import get_config_path, write_default_config

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        # Check permissions (600 = rw-------)
        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_creates_config_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Creates config directory if it doesn't exist."""
        from sentinel.core.config import get_xdg_config_home, write_default_config

        custom_xdg = str(tmp_path / "new-config-dir")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_dir = get_xdg_config_home()

        assert config_dir.exists(), "Config directory should be created"
        assert config_dir.is_dir(), "Should be a directory"

    def test_writes_valid_toml(self, tmp_path: Path) -> None:
        """Writes valid TOML that can be loaded."""
        from sentinel.core.config import load_config, write_default_config

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config = load_config()

        # Should load without error and have default values
        assert config.energy_threshold == "medium", "Should have default energy threshold"

    def test_config_has_documentation_comments(self, tmp_path: Path) -> None:
        """Config file includes helpful comments."""
        from sentinel.core.config import get_config_path, write_default_config

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        content = config_path.read_text()
        assert "# Sentinel Configuration" in content, "Should have header comment"
        assert "energy_threshold" in content, "Should document energy_threshold"

    def test_accepts_custom_config_path(self, tmp_path: Path) -> None:
        """Accepts custom config path argument."""
        from sentinel.core.config import write_default_config

        custom_path = tmp_path / "custom-config.toml"
        write_default_config(custom_path)

        assert custom_path.exists(), "Custom config file should be created"

    def test_atomic_write_cleans_up_temp_file(self, tmp_path: Path) -> None:
        """Uses atomic write pattern without leaving temp files."""
        from sentinel.core.config import get_config_path, write_default_config

        custom_xdg = str(tmp_path)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_xdg}):
            write_default_config()
            config_path = get_config_path()

        # Check no .tmp file remains
        config_dir = config_path.parent
        tmp_files = list(config_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"No temp files should remain: {tmp_files}"


class TestDefaultConfigToml:
    """Tests for DEFAULT_CONFIG_TOML constant."""

    def test_default_config_toml_is_valid_toml(self) -> None:
        """DEFAULT_CONFIG_TOML is valid TOML syntax."""
        import tomllib

        from sentinel.core.config import DEFAULT_CONFIG_TOML

        # Should parse without error
        data = tomllib.loads(DEFAULT_CONFIG_TOML)
        assert "energy_threshold" in data, "Should contain energy_threshold key"

    def test_default_config_toml_matches_defaults(self) -> None:
        """DEFAULT_CONFIG_TOML values match SentinelConfig defaults."""
        import tomllib

        from sentinel.core.config import DEFAULT_CONFIG, DEFAULT_CONFIG_TOML

        data = tomllib.loads(DEFAULT_CONFIG_TOML)
        assert data["energy_threshold"] == DEFAULT_CONFIG.energy_threshold
        assert data["llm_provider"] == DEFAULT_CONFIG.llm_provider
        assert data["default_format"] == DEFAULT_CONFIG.default_format
        assert data["telemetry_enabled"] == DEFAULT_CONFIG.telemetry_enabled


class TestEnergyThresholdConstants:
    """Tests for energy threshold constants (Story 5.2)."""

    def test_energy_threshold_low_is_0_3(self) -> None:
        """ENERGY_THRESHOLD_LOW is 0.3."""
        from sentinel.core.constants import ENERGY_THRESHOLD_LOW

        assert ENERGY_THRESHOLD_LOW == 0.3, f"Expected 0.3, got {ENERGY_THRESHOLD_LOW}"

    def test_energy_threshold_medium_is_0_5(self) -> None:
        """ENERGY_THRESHOLD_MEDIUM is 0.5."""
        from sentinel.core.constants import ENERGY_THRESHOLD_MEDIUM

        assert ENERGY_THRESHOLD_MEDIUM == 0.5, f"Expected 0.5, got {ENERGY_THRESHOLD_MEDIUM}"

    def test_energy_threshold_high_is_0_7(self) -> None:
        """ENERGY_THRESHOLD_HIGH is 0.7."""
        from sentinel.core.constants import ENERGY_THRESHOLD_HIGH

        assert ENERGY_THRESHOLD_HIGH == 0.7, f"Expected 0.7, got {ENERGY_THRESHOLD_HIGH}"

    def test_energy_threshold_map_contains_all_values(self) -> None:
        """ENERGY_THRESHOLD_MAP maps all string values to floats."""
        from sentinel.core.constants import (
            ENERGY_THRESHOLD_HIGH,
            ENERGY_THRESHOLD_LOW,
            ENERGY_THRESHOLD_MAP,
            ENERGY_THRESHOLD_MEDIUM,
        )

        assert "low" in ENERGY_THRESHOLD_MAP, "Map should contain 'low'"
        assert "medium" in ENERGY_THRESHOLD_MAP, "Map should contain 'medium'"
        assert "high" in ENERGY_THRESHOLD_MAP, "Map should contain 'high'"
        assert ENERGY_THRESHOLD_MAP["low"] == ENERGY_THRESHOLD_LOW
        assert ENERGY_THRESHOLD_MAP["medium"] == ENERGY_THRESHOLD_MEDIUM
        assert ENERGY_THRESHOLD_MAP["high"] == ENERGY_THRESHOLD_HIGH


class TestGetConfidenceThreshold:
    """Tests for get_confidence_threshold() function (Story 5.2)."""

    def test_get_confidence_threshold_low(self) -> None:
        """Low threshold returns 0.3."""
        from sentinel.core.config import get_confidence_threshold

        result = get_confidence_threshold("low")
        assert result == 0.3, f"Expected 0.3, got {result}"

    def test_get_confidence_threshold_medium(self) -> None:
        """Medium threshold returns 0.5."""
        from sentinel.core.config import get_confidence_threshold

        result = get_confidence_threshold("medium")
        assert result == 0.5, f"Expected 0.5, got {result}"

    def test_get_confidence_threshold_high(self) -> None:
        """High threshold returns 0.7."""
        from sentinel.core.config import get_confidence_threshold

        result = get_confidence_threshold("high")
        assert result == 0.7, f"Expected 0.7, got {result}"

    def test_get_confidence_threshold_is_exported(self) -> None:
        """get_confidence_threshold is in config module's __all__."""
        from sentinel.core import config

        assert "get_confidence_threshold" in config.__all__, (
            "get_confidence_threshold should be exported in __all__"
        )

    def test_get_confidence_threshold_invalid_returns_medium_fallback(self) -> None:
        """Invalid threshold value falls back to MEDIUM (0.5).

        While validation should catch invalid values earlier, this tests
        the defensive fallback behavior in get_confidence_threshold().
        """
        from sentinel.core.config import get_confidence_threshold
        from sentinel.core.constants import ENERGY_THRESHOLD_MEDIUM

        # Invalid value should return MEDIUM as fallback
        result = get_confidence_threshold("invalid_value")
        assert result == ENERGY_THRESHOLD_MEDIUM, (
            f"Expected MEDIUM fallback ({ENERGY_THRESHOLD_MEDIUM}), got {result}"
        )
