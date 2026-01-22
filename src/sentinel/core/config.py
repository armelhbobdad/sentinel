"""Configuration utilities for Sentinel.

Provides XDG-compliant config path handling and configuration loading.
All configuration is stored in ~/.config/sentinel/ by default, respecting
the XDG_CONFIG_HOME environment variable when set.
"""

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from sentinel.core.exceptions import ConfigError

__all__ = [
    "SentinelConfig",
    "DEFAULT_CONFIG",
    "DEFAULT_CONFIG_TOML",
    "ConfigError",
    "get_xdg_config_home",
    "get_config_path",
    "ensure_config_directory",
    "load_config",
    "write_default_config",
]

# Valid values for Literal fields (used for runtime validation)
VALID_ENERGY_THRESHOLDS: frozenset[str] = frozenset({"low", "medium", "high"})
VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"text", "html"})


def get_xdg_config_home() -> Path:
    """Get XDG config home directory for Sentinel.

    Returns ~/.config/sentinel/ by default.
    Respects XDG_CONFIG_HOME environment variable when set.

    Returns:
        Path to Sentinel's config directory.
    """
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        base = Path(xdg_config_home)
    else:
        base = Path.home() / ".config"
    return base / "sentinel"


def get_config_path() -> Path:
    """Get path to config file.

    Returns:
        Path to config.toml file within Sentinel's config directory.
    """
    return get_xdg_config_home() / "config.toml"


def ensure_config_directory() -> Path:
    """Ensure config directory exists with correct permissions.

    Creates the directory with mkdir -p behavior if it doesn't exist.
    Sets permissions to 700 (owner only) for security.

    Uses umask to prevent race condition where directory is briefly
    accessible before chmod is applied.

    Returns:
        Path to the created/existing config directory.
    """
    config_dir = get_xdg_config_home()

    # Create parent directories with normal permissions (e.g., ~/.config)
    config_dir.parent.mkdir(parents=True, exist_ok=True)

    # Create sentinel directory with restrictive umask to avoid race condition
    if not config_dir.exists():
        old_umask = os.umask(0o077)  # Block group/other access
        try:
            config_dir.mkdir(mode=0o700, exist_ok=True)
        finally:
            os.umask(old_umask)

    # Ensure correct permissions even if dir already existed with wrong perms
    config_dir.chmod(0o700)
    return config_dir


@dataclass(frozen=True)
class SentinelConfig:
    """Sentinel configuration settings.

    All fields have sensible defaults. Config file can be partial.
    """

    # Detection settings (Story 5.2)
    energy_threshold: Literal["low", "medium", "high"] = "medium"

    # LLM settings (Story 5.3)
    llm_provider: str = "openai"
    llm_model: str = "openai/gpt-4o-mini"
    llm_endpoint: str = ""
    embedding_provider: str = "openai"
    embedding_model: str = "openai/text-embedding-3-large"

    # Output settings
    default_format: Literal["text", "html"] = "text"

    # Privacy settings
    telemetry_enabled: bool = False


DEFAULT_CONFIG = SentinelConfig()


def _validate_config_values(data: dict[str, object]) -> None:
    """Validate config values against allowed Literal types.

    Args:
        data: Raw config data from TOML file.

    Raises:
        ConfigError: If any value is not in the allowed set.
    """
    if "energy_threshold" in data:
        value = data["energy_threshold"]
        if value not in VALID_ENERGY_THRESHOLDS:
            raise ConfigError(
                f"Invalid energy_threshold '{value}'. "
                f"Must be one of: {', '.join(sorted(VALID_ENERGY_THRESHOLDS))}"
            )

    if "default_format" in data:
        value = data["default_format"]
        if value not in VALID_OUTPUT_FORMATS:
            raise ConfigError(
                f"Invalid default_format '{value}'. "
                f"Must be one of: {', '.join(sorted(VALID_OUTPUT_FORMATS))}"
            )


# Default config TOML template with documentation comments
DEFAULT_CONFIG_TOML = """\
# Sentinel Configuration
# Location: ~/.config/sentinel/config.toml

# Detection sensitivity: "low", "medium", or "high"
# - low: show collisions with confidence >= 0.3
# - medium: show collisions with confidence >= 0.5 (default)
# - high: show collisions with confidence >= 0.7
energy_threshold = "medium"

# LLM Provider: "openai", "anthropic", or "ollama"
llm_provider = "openai"
llm_model = "openai/gpt-4o-mini"
# llm_endpoint = ""  # Only needed for ollama

# Embedding settings (defaults to OpenAI)
embedding_provider = "openai"
embedding_model = "openai/text-embedding-3-large"

# Output format: "text" or "html"
default_format = "text"

# Privacy settings
telemetry_enabled = false
"""


def load_config(config_path: Path | None = None) -> SentinelConfig:
    """Load configuration from TOML file.

    Args:
        config_path: Optional path override. Defaults to XDG config path.

    Returns:
        SentinelConfig with loaded values merged with defaults.

    Raises:
        ConfigError: If TOML parsing fails.
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        return DEFAULT_CONFIG

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Configuration file is invalid: {e}") from e

    # Validate Literal field values before creating config
    _validate_config_values(data)

    # Merge with defaults - only use keys that are valid SentinelConfig fields
    valid_fields = {f.name for f in fields(SentinelConfig)}
    filtered_data = {k: v for k, v in data.items() if k in valid_fields}

    return SentinelConfig(**{**DEFAULT_CONFIG.__dict__, **filtered_data})


def write_default_config(config_path: Path | None = None) -> None:
    """Write default configuration file with documented settings.

    Creates the config directory if needed. Uses atomic write pattern
    (temp file + rename) to prevent corruption. Sets file permissions
    to 600 (owner read/write only) for security.

    Args:
        config_path: Optional path override. Defaults to XDG config path.
    """
    if config_path is None:
        config_path = get_config_path()
        ensure_config_directory()
    else:
        # Ensure parent directory exists for custom paths with secure permissions
        parent = config_path.parent
        if not parent.exists():
            old_umask = os.umask(0o077)  # Block group/other access
            try:
                parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            finally:
                os.umask(old_umask)
        # Ensure correct permissions even if dir existed
        parent.chmod(0o700)

    temp_path = config_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_TOML)

        # Set permissions before move (0o600 = owner read/write only)
        temp_path.chmod(0o600)
        temp_path.replace(config_path)
    finally:
        # Clean up temp file if it still exists
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
