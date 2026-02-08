"""Configuration management for Josephus CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Default config locations
CONFIG_DIR = Path.home() / ".josephus"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_FILE = ".josephus/config.yml"


def get_config_dir() -> Path:
    """Get the Josephus config directory, creating if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_api_key() -> str | None:
    """Get the API key from environment or config file.

    Returns:
        API key string, or None if not configured
    """
    # First check environment variable
    api_key = os.environ.get("JOSEPHUS_API_KEY")
    if api_key:
        return api_key

    # Then check config file
    config = load_cli_config()
    return config.get("api_key")


def load_cli_config() -> dict[str, Any]:
    """Load CLI configuration from file.

    Returns:
        Configuration dictionary
    """
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def save_cli_config(config: dict[str, Any]) -> None:
    """Save CLI configuration to file.

    Args:
        config: Configuration dictionary to save
    """
    get_config_dir()  # Ensure directory exists

    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)


def load_project_config() -> dict[str, Any]:
    """Load project-level configuration from .josephus/config.yml.

    Returns:
        Configuration dictionary, or empty dict if not found
    """
    config_path = Path(PROJECT_CONFIG_FILE)
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def set_api_key(api_key: str) -> None:
    """Store the API key in the config file.

    Args:
        api_key: API key to store
    """
    config = load_cli_config()
    config["api_key"] = api_key
    save_cli_config(config)


def clear_api_key() -> None:
    """Remove the API key from the config file."""
    config = load_cli_config()
    config.pop("api_key", None)
    save_cli_config(config)


__all__ = [
    "get_api_key",
    "set_api_key",
    "clear_api_key",
    "load_cli_config",
    "save_cli_config",
    "load_project_config",
    "get_config_dir",
]
