"""Input validation and security guards for the web app (UI-free).

Validates the user-entered URL scheme and regex-validates the theme strings before they are ever
injected as CSS.
"""

import re
from urllib.parse import urlparse

_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{3,8}$|^rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)$')
_FONT_FAMILY_RE = re.compile(r"^[\w ,'\"-]+$")
_FONT_SIZE_RE = re.compile(r'^\d{1,3}(px|pt|rem|em|%)$')
_SAFE_URL_SCHEMES = ('', 'http', 'https')


def is_safe_url(url: str) -> bool:
    """Return whether a URL uses an allowed scheme (or is empty).

    Args:
        url: The user-entered playlist/video/token URL.

    Returns:
        bool: True when the scheme is empty, ``http`` or ``https``.
    """
    return urlparse(url.strip()).scheme in _SAFE_URL_SCHEMES


def is_safe_color(value: str) -> bool:
    """Return whether a colour string is a hex or ``rgb(...)`` literal.

    Args:
        value: A theme colour value from config.json.

    Returns:
        bool: True when safe to inject as CSS.
    """
    return bool(_COLOR_RE.match(value.strip()))


def is_safe_font_family(value: str) -> bool:
    """Return whether a font-family string contains only safe characters.

    Args:
        value: A theme font-family value from config.json.

    Returns:
        bool: True when safe to inject as CSS.
    """
    return bool(_FONT_FAMILY_RE.match(value.strip()))


def is_safe_font_size(value: str) -> bool:
    """Return whether a font-size string is a number with a CSS unit.

    Args:
        value: A theme font-size value from config.json.

    Returns:
        bool: True when safe to inject as CSS.
    """
    return bool(_FONT_SIZE_RE.match(value.strip()))
