"""Configuration utilities for Sentinel.

Provides XDG-compliant config path handling and configuration loading.
All configuration is stored in ~/.config/sentinel/ by default, respecting
the XDG_CONFIG_HOME environment variable when set.
"""

import os
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from sentinel.core.constants import ENERGY_THRESHOLD_MAP, ENERGY_THRESHOLD_MEDIUM
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
    "get_confidence_threshold",
    "configure_cognee",
    "validate_api_key",
    "mask_api_key",
    "check_embedding_compatibility",
    "CONFIG_KEYS",
    "get_config_display",
    "get_setting_value",
    "update_config",
    "reset_config",
]

# Valid values for Literal fields (used for runtime validation)
VALID_ENERGY_THRESHOLDS: frozenset[str] = frozenset({"low", "medium", "high"})
VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"text", "html"})
VALID_LLM_PROVIDERS: frozenset[str] = frozenset({"openai", "anthropic", "ollama"})
VALID_EMBEDDING_PROVIDERS: frozenset[str] = frozenset({"openai", "ollama"})
VALID_BOOL_VALUES: frozenset[str] = frozenset({"true", "false"})

# Valid configuration keys with descriptions and allowed values (Story 5.4)
# Format: key -> (description, frozenset of valid values or None for free-form)
CONFIG_KEYS: dict[str, tuple[str, frozenset[str] | None]] = {
    "energy_threshold": (
        "Detection sensitivity (low, medium, high)",
        VALID_ENERGY_THRESHOLDS,
    ),
    "llm_provider": (
        "LLM provider (openai, anthropic, ollama)",
        VALID_LLM_PROVIDERS,
    ),
    "llm_model": (
        "Model identifier (e.g., openai/gpt-5-mini)",
        None,  # Free-form
    ),
    "llm_endpoint": (
        "Custom endpoint URL (required for ollama)",
        None,  # Free-form
    ),
    "embedding_provider": (
        "Embedding provider (openai, ollama)",
        VALID_EMBEDDING_PROVIDERS,
    ),
    "embedding_model": (
        "Embedding model (e.g., openai/text-embedding-3-large)",
        None,  # Free-form
    ),
    "default_format": (
        "Output format (text, html)",
        VALID_OUTPUT_FORMATS,
    ),
    "telemetry_enabled": (
        "Enable Cognee telemetry (true, false)",
        VALID_BOOL_VALUES,
    ),
}


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
    llm_model: str = "openai/gpt-5-mini"
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
llm_model = "openai/gpt-5-mini"
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


def get_confidence_threshold(energy_threshold: str) -> float:
    """Map energy threshold setting to confidence filter value.

    Args:
        energy_threshold: One of "low", "medium", "high".

    Returns:
        Confidence threshold value (0.3, 0.5, or 0.7).

    Note:
        Invalid values should be caught by _validate_config_values() earlier.
        If somehow an invalid value reaches here, returns MEDIUM as fallback.
    """
    return ENERGY_THRESHOLD_MAP.get(energy_threshold, ENERGY_THRESHOLD_MEDIUM)


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


def configure_cognee(config: SentinelConfig | None = None) -> None:
    """Configure Cognee with Sentinel settings.

    Sets environment variables that Cognee reads for LLM and embedding
    configuration. Must be called before any Cognee operations.

    Args:
        config: Optional SentinelConfig. Loads from file if not provided.

    Environment Variables Set:
        - LLM_PROVIDER: The LLM provider (openai, anthropic, ollama)
        - LLM_MODEL: The LLM model to use
        - LLM_ENDPOINT: Custom endpoint (only if non-empty, for ollama)
        - EMBEDDING_PROVIDER: The embedding provider
        - EMBEDDING_MODEL: The embedding model to use
        - TELEMETRY_DISABLED: Set to "1" if telemetry is disabled (NFR9)
    """
    if config is None:
        config = load_config()

    # LLM settings
    os.environ["LLM_PROVIDER"] = config.llm_provider
    os.environ["LLM_MODEL"] = config.llm_model

    # Only set endpoint if non-empty (typically for Ollama)
    if config.llm_endpoint:
        os.environ["LLM_ENDPOINT"] = config.llm_endpoint

    # Embedding settings
    os.environ["EMBEDDING_PROVIDER"] = config.embedding_provider
    os.environ["EMBEDDING_MODEL"] = config.embedding_model

    # Privacy (NFR9: telemetry opt-in only)
    if not config.telemetry_enabled:
        os.environ["TELEMETRY_DISABLED"] = "1"


def validate_api_key() -> str:
    """Validate that an API key is available.

    Cognee uses LLM_API_KEY as the single universal key for all providers.
    The provider is determined by LLM_PROVIDER, not the key name.

    Returns:
        The found API key (stripped of leading/trailing whitespace).

    Raises:
        ConfigError: If LLM_API_KEY is not set or contains only whitespace.
    """
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if api_key:
        return api_key

    raise ConfigError("No API key found. Set LLM_API_KEY environment variable.")


def mask_api_key(key: str) -> str:
    """Mask an API key for safe logging.

    Preserves the first 3 characters and last 4 characters,
    replacing the middle with "...".

    Args:
        key: The API key to mask.

    Returns:
        Masked key (e.g., "sk-...wxyz") or "***" for short/empty keys.
    """
    if len(key) < 8:
        return "***"

    return f"{key[:3]}...{key[-4:]}"


def check_embedding_compatibility(config: SentinelConfig) -> None:
    """Check if embedding configuration is compatible with available API keys.

    Cognee defaults to OpenAI for embeddings. This function validates that
    LLM_API_KEY is available when using OpenAI embeddings.

    Args:
        config: The SentinelConfig to validate.

    Raises:
        ConfigError: If OpenAI embeddings configured but LLM_API_KEY not set.
    """
    # Non-OpenAI embedding providers don't require the key check
    if config.embedding_provider.lower() != "openai":
        return

    # Check if we have LLM_API_KEY (stripped of whitespace for consistency)
    if os.environ.get("LLM_API_KEY", "").strip():
        return

    # No key available - provide helpful error
    error_msg = "Embedding requires API key. Set LLM_API_KEY environment variable."
    error_msg += (
        "\n\nTip: Cognee uses OpenAI for embeddings by default. "
        "For local-only setup, use Ollama embeddings:\n"
        "  sentinel config embedding_provider ollama\n"
        "  sentinel config embedding_model nomic-embed-text:latest"
    )

    raise ConfigError(error_msg)


def get_config_display(config: SentinelConfig) -> str:
    """Format all configuration for display with section headers.

    Args:
        config: The SentinelConfig to format.

    Returns:
        Human-readable string with all settings grouped by category.
    """
    lines = []

    # LLM Settings
    lines.append("# LLM Settings")
    lines.append(f"llm_provider: {config.llm_provider}")
    lines.append(f"llm_model: {config.llm_model}")
    endpoint_display = config.llm_endpoint if config.llm_endpoint else "(not set)"
    lines.append(f"llm_endpoint: {endpoint_display}")
    lines.append("")

    # Embedding Settings
    lines.append("# Embedding Settings")
    lines.append(f"embedding_provider: {config.embedding_provider}")
    lines.append(f"embedding_model: {config.embedding_model}")
    lines.append("")

    # Detection Settings
    lines.append("# Detection Settings")
    lines.append(f"energy_threshold: {config.energy_threshold}")
    lines.append("")

    # Output Settings
    lines.append("# Output")
    lines.append(f"default_format: {config.default_format}")
    lines.append("")

    # Privacy Settings
    lines.append("# Privacy")
    telemetry_str = "true" if config.telemetry_enabled else "false"
    lines.append(f"telemetry_enabled: {telemetry_str}")

    return "\n".join(lines)


def get_setting_value(config: SentinelConfig, key: str) -> str:
    """Get a single setting value for display.

    Args:
        config: The SentinelConfig to read from.
        key: Configuration key to retrieve.

    Returns:
        String representation of the setting value.

    Raises:
        ConfigError: If key is not a valid configuration key.
    """
    if key not in CONFIG_KEYS:
        valid_keys = ", ".join(sorted(CONFIG_KEYS.keys()))
        raise ConfigError(f"Unknown configuration key '{key}'. Valid keys: {valid_keys}")

    value = getattr(config, key)

    # Handle special cases
    if key == "llm_endpoint" and not value:
        return "(not set)"
    if key == "telemetry_enabled":
        return "true" if value else "false"

    return str(value)


def update_config(key: str, value: str, config_path: Path | None = None) -> None:
    """Update a single configuration value.

    Loads existing config, updates the key, validates, and writes back.
    Uses regex-based update to preserve comments in the TOML file.

    Args:
        key: Configuration key to update.
        value: New value (will be converted to appropriate type).
        config_path: Optional path override. Defaults to XDG config path.

    Raises:
        ConfigError: If key is invalid or value doesn't pass validation.
    """
    if key not in CONFIG_KEYS:
        valid_keys = ", ".join(sorted(CONFIG_KEYS.keys()))
        raise ConfigError(f"Unknown configuration key '{key}'. Valid keys: {valid_keys}")

    # Validate value against allowed values if specified
    description, valid_values = CONFIG_KEYS[key]
    if valid_values is not None and value.lower() not in valid_values:
        valid_list = ", ".join(sorted(valid_values))
        raise ConfigError(f"Invalid value '{value}' for {key}. Valid values: {valid_list}")

    if config_path is None:
        config_path = get_config_path()

    # Create config file with defaults if it doesn't exist
    if not config_path.exists():
        write_default_config(config_path)

    content = config_path.read_text()

    # Convert value to TOML format
    if key == "telemetry_enabled":
        toml_value = "true" if value.lower() == "true" else "false"
    else:
        # Quote string values
        toml_value = f'"{value}"'

    # Regex to find and replace the key's value
    pattern = rf"^({re.escape(key)}\s*=\s*).*$"
    replacement = rf"\g<1>{toml_value}"

    if re.search(pattern, content, re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        # Key doesn't exist - append it
        new_content = content.rstrip() + f"\n{key} = {toml_value}\n"

    # Write atomically
    temp_path = config_path.with_suffix(".tmp")
    try:
        temp_path.write_text(new_content)
        temp_path.chmod(0o600)
        temp_path.replace(config_path)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def reset_config(config_path: Path | None = None) -> None:
    """Reset configuration to default values.

    Overwrites the config file with DEFAULT_CONFIG_TOML.

    Args:
        config_path: Optional path override. Defaults to XDG config path.
    """
    write_default_config(config_path)
