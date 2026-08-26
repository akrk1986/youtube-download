"""Video metadata retrieval using yt-dlp."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yt_dlp

from funcs_utils import (get_cookie_args, is_format_error,
                         retry_on_facebook_parse_error, sanitize_url_for_subprocess)
from funcs_video_info.url_validation import get_timeout_for_url

logger = logging.getLogger(__name__)


class EmptyPlaylistError(RuntimeError):
    """Raised when a URL is a valid playlist but contains no entries.

    A subclass of RuntimeError so existing ``except RuntimeError`` callers keep working, while
    callers that care can distinguish an empty playlist from a genuine enumeration failure.
    """


class _SilentLogger:
    """Custom logger for yt-dlp that suppresses format errors."""

    def debug(self, msg: str) -> None:
        """Suppress debug messages."""

    def info(self, msg: str) -> None:
        """Suppress info messages."""

    def warning(self, msg: str) -> None:
        """Suppress warning messages."""

    def error(self, msg: str) -> None:
        """Log non-format errors at debug level; suppress format errors."""
        # Suppress format errors, log others at debug level
        if not is_format_error(msg):
            logger.debug(f'yt-dlp error: {msg}')


def _run_info_probe(cmd: list[str], timeout: int, url: str) -> subprocess.CompletedProcess[str]:
    """Run the yt-dlp metadata probe subprocess, mapping a timeout to RuntimeError."""
    try:
        return subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {timeout} seconds for URL '{url}'") from None


def get_video_info(yt_dlp_path: Path, url: str, video_download_timeout: int | None = None) -> dict[str, Any]:
    """Get video information using yt-dlp by requesting the meta-data as JSON, w/o download of the video."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=url, video_download_timeout=video_download_timeout)

    base_cmd = [
        str(yt_dlp_path),
        '--no-warnings',
        '--ignore-config',
        '--dump-json',
        '--no-download',
        sanitized_url
    ]

    # Add cookie arguments if configured via environment variable
    cookie_args = get_cookie_args()
    cmd = base_cmd[:1] + cookie_args + base_cmd[1:]

    def _attempt(attempt_number: int) -> subprocess.CompletedProcess[str]:
        """Run one probe, dropping the browser cookies from every attempt after the first.

        Args:
            attempt_number: The 1-based attempt number supplied by the retry helper.

        Returns:
            subprocess.CompletedProcess[str]: The completed yt-dlp probe.
        """
        probe_cmd = cmd if attempt_number == 1 else base_cmd
        return _run_info_probe(cmd=probe_cmd, timeout=timeout, url=url)

    logger.debug(f'Getting video info with timeout of {timeout} seconds')
    try:
        result = retry_on_facebook_parse_error(attempt=_attempt, url=url, label='Metadata probe')
    except subprocess.CalledProcessError as e:
        # Check if this is a format error - return empty dict instead of raising
        if is_format_error(e.stderr):
            logger.debug(f'Format not available for URL, returning empty info: {url}')
            return {}
        raise RuntimeError(f'yt-dlp failed: {e.stderr}') from e

    # Try to parse as single JSON object first
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        # If parsing fails due to multiple JSON objects (playlist), parse only the first one
        if 'Extra data' in str(e):
            logger.warning('Multiple JSON objects detected in yt-dlp output, parsing first object only')
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        raise RuntimeError(f"Failed to parse yt-dlp output for '{url}': {e}") from e


def _cookie_browser() -> str:
    """Return the browser whose cookies yt-dlp should use, or an empty string when none is set.

    Returns:
        str: 'chrome', 'firefox', or '' when YTDLP_USE_COOKIES is unset/empty.
    """
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if not cookie_env:
        return ''
    return 'chrome' if cookie_env.lower() == 'chrome' else 'firefox'


def _build_flat_ydl_opts(with_cookies: bool = True) -> dict[str, Any]:
    """yt-dlp options for flat metadata extraction (no download). Includes cookies if set.

    Args:
        with_cookies: Whether to pass the browser cookies named by YTDLP_USE_COOKIES. False drives
            the cookie-less retry in is_playlist().

    Returns:
        dict[str, Any]: The yt-dlp option dict.
    """
    ydl_opts: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': _SilentLogger(),
    }
    browser = _cookie_browser() if with_cookies else ''
    if browser:
        ydl_opts['cookiesfrombrowser'] = (browser,)
    return ydl_opts


def _extract_flat(url: str, with_cookies: bool) -> dict[str, Any] | None:
    """Run one flat (no-download) extraction, letting yt-dlp's own errors propagate.

    Args:
        url: The URL to probe.
        with_cookies: Whether to pass the configured browser cookies.

    Returns:
        dict[str, Any] | None: The extracted info, or None when yt-dlp returns nothing.
    """
    ydl_opts = _build_flat_ydl_opts(with_cookies=with_cookies)
    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:  # type: ignore
        return ydl.extract_info(url=url, download=False)  # type: ignore[return-value]


def _extract_flat_with_cookie_retry(url: str) -> dict[str, Any] | None:
    """Run the flat probe, retrying once without the browser cookies when the first attempt used them.

    YouTube rejects a session it considers stale ('The page needs to be reloaded.'), which a live
    browser rotating the cookies yt-dlp copied produces routinely. The cookies only matter for
    restricted videos, so a second, cookie-less attempt answers the question for everything else.
    This is the retry get_video_info() already does, where _attempt() drops the cookies after the
    first try. A format error is not a session problem, so it is raised without a retry.

    Args:
        url: The URL to probe.

    Returns:
        dict[str, Any] | None: The extracted info, or None when yt-dlp returns nothing.

    Raises:
        Exception: Whatever yt-dlp raised on the final attempt.
    """
    for with_cookies in (True, False):
        if with_cookies and not _cookie_browser():
            continue  # no cookies to drop — go straight to the cookie-less attempt
        try:
            return _extract_flat(url=url, with_cookies=with_cookies)
        except Exception as e:  # pylint: disable=broad-except
            if not with_cookies or is_format_error(str(e)):
                raise
            logger.debug(f'Flat probe with browser cookies failed ({e}) — retrying without them')
    return None  # unreachable: the cookie-less attempt either returns or raises


def is_playlist(url: str) -> bool:
    """Check if url is a playlist, w/o downloading.
    Using the yt-dlp Python library."""
    try:
        info = _extract_flat_with_cookie_retry(url=url)
    except Exception as e:  # pylint: disable=broad-except
        if is_format_error(str(e)):
            logger.debug(f'Format not available for URL, assuming not a playlist: {url}')
        else:
            logger.error(f"Failed to get video info for URL '{url}': {e}")
        return False
    return info is not None and info.get('webpage_url_basename') == 'playlist'


def get_playlist_entries(url: str) -> list[tuple[str, str]]:
    """Return [(title, watch_url), ...] for a YouTube playlist URL.

    Uses the yt-dlp Python library with extract_flat so it never downloads media.
    Builds the per-entry watch URL from the entry id when 'url' is absent.
    Raises EmptyPlaylistError if the playlist has no entries, or RuntimeError if extraction fails."""
    try:
        info = _extract_flat_with_cookie_retry(url=url)
    except Exception as e:
        raise RuntimeError(f"Failed to enumerate playlist '{url}': {e}") from e

    entries = (info or {}).get('entries') or []
    if not entries:
        raise EmptyPlaylistError(f"No playlist entries found for URL '{url}'")

    result: list[tuple[str, str]] = []
    for entry in entries:  # type: ignore[union-attr]
        if entry is None:
            continue
        title = entry.get('title') or '<unknown title>'
        watch_url = entry.get('url') or entry.get('webpage_url')
        if not watch_url:
            entry_id = entry.get('id')
            if entry_id:
                watch_url = f'https://www.youtube.com/watch?v={entry_id}'
            else:
                logger.warning(f"Skipping playlist entry without id or url: {entry!r}")
                continue
        result.append((title, watch_url))
    return result
