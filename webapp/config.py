"""Configuration loading for the web app (UI-free).

Reads ``webapp/config.json`` into typed dataclasses, then lets a ``WEBAPP_HOST`` / ``WEBAPP_PORT``
environment variable and finally an explicit CLI ``--host`` / ``--port`` override the file value
(precedence: CLI > env > config.json > built-in default). Only non-secret settings live in the
JSON; the NiceGUI ``storage_secret`` is imported from the gitignored top-level ``git_excluded.py``
by the app module, not from here.
"""

import json
import os
import platform
import sys
from dataclasses import dataclass, replace
from pathlib import Path

CONFIG_FILENAME: str = 'config.json'
DEFAULT_PORT: int = 8081
# Chrome, the UI font. Deliberately not Roboto: the app is a local control surface, so a webfont
# would add a network dependency for no gain — this stack asks each platform for its own native UI
# face instead, and only reaches a generic as a last resort.
DEFAULT_FONT_FAMILY: str = ("'Segoe UI Variable Text', 'Segoe UI', Cantarell, 'DejaVu Sans', "
                            'system-ui, sans-serif')
# The output log. A bare 'monospace' resolves to Courier New on Windows, whose thin strokes and
# broken box-drawing coverage mangle the linters' rich tables; every face named here draws
# U+2500-257F at a full cell.
DEFAULT_MONO_FAMILY: str = ("'Cascadia Mono', Consolas, 'SF Mono', Menlo, 'DejaVu Sans Mono', "
                            "'Liberation Mono', ui-monospace, monospace")
# Binding to all interfaces is intentional: reachable across the local 192.168.1.x / 10.0.0.x
# subnets (no external exposure).
DEFAULT_HOST: str = '0.0.0.0'  # nosec B104
_COOKIE_CHOICES = ('none', 'firefox', 'chrome')


@dataclass(frozen=True)
class ThemeConfig:
    """Visual theme pulled from config.json (validated before use)."""

    dark: bool
    fg_color: str
    bg_color: str
    font_family: str
    font_size: str
    output_font_family: str
    output_font_size: str


@dataclass(frozen=True)
class AppConfig:
    """Top-level web-app configuration."""

    host: str
    port: int
    native: bool
    reload: bool
    boost_default: float
    default_cookies: str
    theme: ThemeConfig


def default_theme_colors(dark: bool) -> tuple[str, str]:
    """Return the (foreground, background) pair that matches a dark or light theme.

    Keeping these derived from ``dark`` means a config.json that flips ``dark`` without also
    restating the colours stays coherent, instead of drawing light Quasar controls on a dark body.
    Public because the page reuses the same pair as its fallback when a configured colour is
    rejected by validation, so a bad value lands on the theme's own default rather than a fixed one.

    Args:
        dark: The theme's ``dark`` flag.

    Returns:
        tuple[str, str]: The default foreground and background colours for that theme.
    """
    return ('#e8e8e8', '#1e1e1e') if dark else ('#1f1f1f', '#fafafa')


def load_config(config_path: Path) -> AppConfig:
    """Load and normalise the web-app configuration from a JSON file.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        AppConfig: The parsed configuration (before any env/CLI host/port override).
    """
    raw = json.loads(config_path.read_text(encoding='utf-8'))

    theme_raw = raw.get('theme', {})
    # `dark` is the single source of truth: an omitted (or blank) fg/bg colour follows it, so the
    # body background and the Quasar component theme can never disagree by accident.
    dark = bool(theme_raw.get('dark', True))
    default_fg, default_bg = default_theme_colors(dark=dark)
    theme = ThemeConfig(
        dark=dark,
        fg_color=str(theme_raw.get('fg_color') or default_fg),
        bg_color=str(theme_raw.get('bg_color') or default_bg),
        font_family=str(theme_raw.get('font_family') or DEFAULT_FONT_FAMILY),
        font_size=theme_raw.get('font_size', '16px'),
        output_font_family=str(theme_raw.get('output_font_family') or DEFAULT_MONO_FAMILY),
        output_font_size=theme_raw.get('output_font_size', '13px'),
    )
    configured_cookies = str(raw.get('cookies', '')).strip().lower()
    default_cookies = configured_cookies if configured_cookies in _COOKIE_CHOICES \
        else _platform_default_cookies()
    return AppConfig(
        host=raw.get('host', DEFAULT_HOST),
        port=int(raw.get('port', DEFAULT_PORT)),
        native=bool(raw.get('native', False)),
        reload=bool(raw.get('reload', False)),
        boost_default=float(raw.get('boost_default', 2.0)),
        default_cookies=default_cookies,
        theme=theme,
    )


def _platform_default_cookies() -> str:
    """Return the platform-appropriate default cookie source for presets.

    Native Windows can read its Firefox profile in place; WSL/Linux/macOS cannot reach the Windows
    Firefox profile (and usually have none of their own), so they default to no cookies. Overridden
    by a ``cookies`` value in config.json.

    Returns:
        str: 'firefox' on native Windows, 'none' elsewhere.
    """
    return 'firefox' if sys.platform == 'win32' else 'none'


def is_wsl() -> bool:
    """Return whether the app is running under Windows Subsystem for Linux (not native Linux).

    Uses two independent signals: the WSL-only environment variables, and the ``microsoft`` marker in
    the kernel release (e.g. ``5.15.167.4-microsoft-standard-WSL2``). Windows and native Linux both
    return False.

    Returns:
        bool: True under WSL, False on Windows, macOS, and native Linux.
    """
    if sys.platform != 'linux':
        return False
    if os.environ.get('WSL_DISTRO_NAME') or os.environ.get('WSL_INTEROP'):
        return True
    return 'microsoft' in platform.uname().release.lower()


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
