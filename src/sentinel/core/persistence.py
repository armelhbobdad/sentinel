"""Persistence utilities for Sentinel graphs.

Provides XDG-compliant path handling and graph serialization/deserialization.
All data is stored in ~/.local/share/sentinel/ by default, respecting
the XDG_DATA_HOME environment variable when set.
"""

import os
from pathlib import Path


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
