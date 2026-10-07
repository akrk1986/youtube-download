"""Clipboard watcher for YouTube/Facebook URLs (UI-free).

Polls the OS clipboard (via pyperclip, off the event loop) while enabled and invokes a callback when
a *new* media URL is copied — a YouTube video, playlist, youtu.be, or shorts link, or a Facebook
video link (whatever the main script would accept). A link copied out of a Gmail message arrives
wrapped in a Google redirect (``google.com/url?q=<encoded target>&…``); the watcher unwraps it and
delivers the clean inner URL. Holds no NiceGUI references — the UI layer drives ``poll()`` from a
``ui.timer`` and supplies the callback for updating the URL field.

An unreadable clipboard (empty / non-text, or no Linux backend) is treated as "nothing new this
tick" and skipped silently — notably, WSL's PowerShell-backed clipboard *raises* on an empty
clipboard, which is a normal state, not a failure. The watcher keeps running so the next real copy
is picked up.
"""

import asyncio
from collections.abc import Callable

import pyperclip

from funcs_utils.media_url import extract_media_url


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
    """Polls the clipboard while enabled and reports new YouTube/Facebook URLs via a callback."""

    def __init__(self, *, on_media_url: Callable[[str], None]) -> None:
        """Store the callback; the watcher starts disabled.

        Args:
            on_media_url: Called with the URL when a new YouTube/Facebook link is copied while
                enabled.
        """
        self._on_media_url = on_media_url
        self._enabled = False
        self._last_seen: str | None = None

    def start(self) -> None:
        """Enable watching and immediately deliver a media URL already on the clipboard.

        The natural flow is copy-the-link-first, then click 'Start watching' — so a media URL
        sitting on the clipboard when watching starts is delivered right away. Either way the
        current clipboard becomes the baseline, so it will not re-trigger on the next poll (and
        re-copying the identical value never can — the poll only sees changes). An unreadable
        clipboard seeds None (harmless).
        """
        self._enabled = True
        self._last_seen = _safe_paste()
        if self._last_seen is not None:
            media_url = extract_media_url(self._last_seen)
            if media_url is not None:
                self._on_media_url(media_url)

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
        """Check the clipboard once and fire the callback on a new media URL (no-op while disabled).

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
        media_url = extract_media_url(value)
        if media_url is not None:
            self._on_media_url(media_url)
