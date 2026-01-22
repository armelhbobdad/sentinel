"""Integration tests for configuration persistence.

Tests end-to-end config file operations using temp directories.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel.core.config import (
    DEFAULT_CONFIG,
    get_config_path,
    get_xdg_config_home,
    load_config,
    write_default_config,
)


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
