"""Configuration loading for the web app (UI-free).

Reads ``webapp/config.json`` into typed dataclasses, then lets a ``WEBAPP_HOST`` / ``WEBAPP_PORT``
environment variable and finally an explicit CLI ``--host`` / ``--port`` override the file value
(precedence: CLI > env > config.json > built-in default). Only non-secret settings live in the
JSON; the NiceGUI ``storage_secret`` is imported from the gitignored top-level ``git_excluded.py``
by the app module, not from here.
"""

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

CONFIG_FILENAME: str = 'config.json'
DEFAULT_PORT: int = 8081
# Binding to all interfaces is intentional: reachable across the local 192.168.1.x / 10.0.0.x
# subnets (no external exposure).
DEFAULT_HOST: str = '0.0.0.0'  # nosec B104


@dataclass(frozen=True)
class ThemeConfig:
    """Visual theme pulled from config.json (validated before use)."""

    dark: bool
    fg_color: str
    bg_color: str
    font_family: str
    font_size: str
    output_font_size: str


@dataclass(frozen=True)
class AppConfig:
    """Top-level web-app configuration."""

    host: str
    port: int
    native: bool
    reload: bool
    boost_default: float
    theme: ThemeConfig


def load_config(config_path: Path) -> AppConfig:
    """Load and normalise the web-app configuration from a JSON file.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        AppConfig: The parsed configuration (before any env/CLI host/port override).
    """
    raw = json.loads(config_path.read_text(encoding='utf-8'))

    theme_raw = raw.get('theme', {})
    theme = ThemeConfig(
        dark=bool(theme_raw.get('dark', True)),
        fg_color=theme_raw.get('fg_color', '#e8e8e8'),
        bg_color=theme_raw.get('bg_color', '#1e1e1e'),
        font_family=theme_raw.get('font_family', 'Roboto, sans-serif'),
        font_size=theme_raw.get('font_size', '16px'),
        output_font_size=theme_raw.get('output_font_size', '13px'),
    )
    return AppConfig(
        host=raw.get('host', DEFAULT_HOST),
        port=int(raw.get('port', DEFAULT_PORT)),
        native=bool(raw.get('native', False)),
        reload=bool(raw.get('reload', False)),
        boost_default=float(raw.get('boost_default', 2.0)),
        theme=theme,
    )


def resolve_host_port(config: AppConfig, cli_host: str | None, cli_port: int | None) -> AppConfig:
    """Apply the env and CLI host/port overrides on top of the file-derived config.

    Precedence (highest first): explicit CLI argument, ``WEBAPP_HOST`` / ``WEBAPP_PORT`` env var,
    the value already in ``config`` (from config.json or its default).

    Args:
        config: The configuration parsed from config.json.
        cli_host: Host from the ``--host`` CLI argument, or None when not given.
        cli_port: Port from the ``--port`` CLI argument, or None when not given.

    Returns:
        AppConfig: A copy with the effective host and port.
    """
    env_host = os.getenv('WEBAPP_HOST')
    env_port = os.getenv('WEBAPP_PORT')
    host = cli_host or env_host or config.host
    port = cli_port if cli_port is not None else int(env_port) if env_port else config.port
    return replace(config, host=host, port=port)
