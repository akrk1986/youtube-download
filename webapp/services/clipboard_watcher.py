"""Clipboard watcher for YouTube URLs (UI-free).

Polls the OS clipboard (via pyperclip, off the event loop) while enabled and invokes a callback when
a *new* YouTube URL is copied. Holds no NiceGUI references — the UI layer drives ``poll()`` from a
``ui.timer`` and supplies the callback for updating the URL field.

An unreadable clipboard (empty / non-text, or no Linux backend) is treated as "nothing new this
tick" and skipped silently — notably, WSL's PowerShell-backed clipboard *raises* on an empty
clipboard, which is a normal state, not a failure. The watcher keeps running so the next real copy
is picked up.
"""

import asyncio
import re
from collections.abc import Callable

import pyperclip

# Matches youtube.com/watch?v=…, youtu.be/<id>, and m.youtube.com/watch?v=… (optional scheme/www/m).
_YOUTUBE_RE = re.compile(
    r'^(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/)',
    re.IGNORECASE,
)


def _is_youtube_url(value: str) -> bool:
    """Return whether a string looks like a YouTube watch URL.

    Args:
        value: A candidate clipboard string.

    Returns:
        bool: True for youtube.com/watch?v=, youtu.be/, or m.youtube.com watch links.
    """
    return bool(_YOUTUBE_RE.match(value.strip()))


def _safe_paste() -> str | None:
    """Read the clipboard, returning None when it cannot be read.

    Swallows every pyperclip error (empty/non-text clipboard, or a missing Linux backend) so a
    routine empty clipboard never disrupts the poll loop.

    Returns:
        str | None: The clipboard text, or None when it cannot be read.
    """
    try:
        return pyperclip.paste()
    except Exception:  # noqa: BLE001 - empty/non-text clipboard or missing backend: skip this tick
        return None


class ClipboardWatcher:
    """Polls the clipboard while enabled and reports new YouTube URLs via a callback."""

    def __init__(self, *, on_youtube_url: Callable[[str], None]) -> None:
        """Store the callback; the watcher starts disabled.

        Args:
            on_youtube_url: Called with the URL when a new YouTube link is copied while enabled.
        """
        self._on_youtube_url = on_youtube_url
        self._enabled = False
        self._last_seen: str | None = None

    def start(self) -> None:
        """Enable watching, seeding last-seen with the current clipboard so it will not re-trigger.

        A URL copied before (or while) watching was off is recorded as the baseline here, so
        re-enabling does not immediately fire on it. An unreadable clipboard seeds None (harmless).
        """
        self._enabled = True
        self._last_seen = _safe_paste()

    def stop(self) -> None:
        """Disable watching."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Return whether watching is currently enabled.

        Returns:
            bool: True while enabled.
        """
        return self._enabled

    async def poll(self) -> None:
        """Check the clipboard once and fire the callback on a new YouTube URL (no-op while disabled).

        Reads the clipboard on a worker thread so a slow/blocking ``pyperclip.paste()`` never stalls
        the shared NiceGUI event loop. An unreadable read (None) is skipped; the callback runs on the
        event loop, not the worker thread.
        """
        if not self._enabled:
            return
        value = await asyncio.to_thread(_safe_paste)
        if value is None or value == self._last_seen:
            return
        self._last_seen = value
        if _is_youtube_url(value):
            self._on_youtube_url(value)
