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
import re
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pyperclip

# Matches the YouTube URL forms yt-dlp accepts, so the watcher never rejects a link the main script
# would happily download: a video (watch?v=…), a playlist (playlist?list=…), a youtu.be/<id> short
# link, or a shorts/<id> link — with an optional scheme and www./m./music. subdomain. A watch link
# that also carries a &list=… playlist matches via the watch?v= branch.
_YOUTUBE_RE = re.compile(
    r'^(?:https?://)?(?:www\.|m\.|music\.)?'
    r'(?:youtube\.com/(?:watch\?v=|playlist\?list=|shorts/)|youtu\.be/)',
    re.IGNORECASE,
)

# Matches the Facebook video URL forms yt-dlp accepts: a watch link (watch?v=… / watch/?v=…), a
# page/user video permalink (<page>/videos/<id>), the legacy video.php?v=… form, a reel, a share
# link (share/v/… or share/r/…), or an fb.watch/<id> short link — with an optional scheme and
# www./m./web. subdomain. A bare profile/page URL (facebook.com/<page>) deliberately does NOT match.
_FACEBOOK_RE = re.compile(
    r'^(?:https?://)?'
    r'(?:(?:www\.|m\.|web\.)?facebook\.com/'
    r'(?:watch/?\?v=|video\.php\?v=|reel/|share/[rv]/|[^/?#]+/videos/)'
    r'|fb\.watch/)',
    re.IGNORECASE,
)


# Matches the Google redirect wrapper Gmail puts around links in messages: right-clicking a link
# in a Gmail message and copying it yields 'https://www.google.com/url?q=<encoded target>&source=
# gmail&…' (country TLDs like google.co.il appear too), not the target URL itself.
_GOOGLE_REDIRECT_RE = re.compile(
    r'^(?:https?://)?(?:www\.)?google\.[a-z]{2,3}(?:\.[a-z]{2})?/url\?',
    re.IGNORECASE,
)


def _unwrap_google_redirect(value: str) -> str:
    """Return the target URL from a Google/Gmail redirect wrapper, or the value unchanged.

    Args:
        value: A candidate clipboard string (already stripped).

    Returns:
        str: The URL-decoded ``q`` (or ``url``) query parameter when the value is a
            ``google.com/url?…`` redirect carrying one, otherwise the value as-is.
    """
    if not _GOOGLE_REDIRECT_RE.match(value):
        return value
    query = parse_qs(urlparse(value).query)
    for param in ('q', 'url'):
        target = query.get(param)
        if target and target[0].strip():
            return target[0].strip()
    return value


def _extract_media_url(value: str) -> str | None:
    """Return the media URL carried by a clipboard value, or None when there is none.

    Unwraps a Gmail/Google redirect first, so a link copied out of a Gmail message is
    recognised and delivered as the clean target URL.

    Args:
        value: A candidate clipboard string.

    Returns:
        str | None: The (unwrapped, stripped) media URL, or None when the value is not one.
    """
    candidate = _unwrap_google_redirect(value.strip())
    return candidate if _is_media_url(candidate) else None


def _is_media_url(value: str) -> bool:
    """Return whether a string looks like a downloadable YouTube or Facebook video URL.

    Args:
        value: A candidate clipboard string.

    Returns:
        bool: True for YouTube watch/playlist/shorts/youtu.be links and Facebook video links
            (watch?v=, <page>/videos/, video.php?v=, reel, share, fb.watch).
    """
    stripped = value.strip()
    return bool(_YOUTUBE_RE.match(stripped) or _FACEBOOK_RE.match(stripped))


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
            media_url = _extract_media_url(self._last_seen)
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
        media_url = _extract_media_url(value)
        if media_url is not None:
            self._on_media_url(media_url)
