"""Video metadata retrieval using yt-dlp."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yt_dlp

from funcs_utils import (get_cookie_args, is_facebook_parse_error,
                         is_format_error, sanitize_url_for_subprocess)
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

    logger.debug(f'Getting video info with timeout of {timeout} seconds')
    try:
        result = _run_info_probe(cmd=cmd, timeout=timeout, url=url)
    except subprocess.CalledProcessError as e:
        # Check if this is a format error - return empty dict instead of raising
        if is_format_error(e.stderr):
            logger.debug(f'Format not available for URL, returning empty info: {url}')
            return {}
        if not (cookie_args and is_facebook_parse_error(url=url, error_text=e.stderr)):
            raise RuntimeError(f'yt-dlp failed: {e.stderr}') from e
        # Logged-in Facebook serves a page variant yt-dlp may fail to parse; the same URL
        # usually works anonymously, so retry the probe once without the browser cookies.
        logger.warning("Facebook metadata probe failed with browser cookies ('Cannot parse data'), "
                       'retrying without cookies')
        try:
            result = _run_info_probe(cmd=base_cmd, timeout=timeout, url=url)
        except subprocess.CalledProcessError as retry_error:
            raise RuntimeError(f'yt-dlp failed: {retry_error.stderr}') from retry_error

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


def _build_flat_ydl_opts() -> dict[str, Any]:
    """yt-dlp options for flat metadata extraction (no download). Includes cookies if set."""
    ydl_opts: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': _SilentLogger(),
    }
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if cookie_env:
        browser = 'chrome' if cookie_env.lower() == 'chrome' else 'firefox'
        ydl_opts['cookiesfrombrowser'] = (browser,)
    return ydl_opts


def is_playlist(url: str) -> bool:
    """Check if url is a playlist, w/o downloading.
    Using the yt-dlp Python library."""
    ydl_opts = _build_flat_ydl_opts()
    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:  # type: ignore
        try:
            info = ydl.extract_info(url=url, download=False)
            return info.get('webpage_url_basename') == 'playlist'  # type: ignore[typeddict-item]
        except Exception as e:
            error_str = str(e)
            if is_format_error(error_str):
                logger.debug(f'Format not available for URL, assuming not a playlist: {url}')
            else:
                logger.error(f"Failed to get video info for URL '{url}': {e}")
            return False


def get_playlist_entries(url: str) -> list[tuple[str, str]]:
    """Return [(title, watch_url), ...] for a YouTube playlist URL.

    Uses the yt-dlp Python library with extract_flat so it never downloads media.
    Builds the per-entry watch URL from the entry id when 'url' is absent.
    Raises EmptyPlaylistError if the playlist has no entries, or RuntimeError if extraction fails."""
    ydl_opts = _build_flat_ydl_opts()
    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:  # type: ignore
        try:
            info = ydl.extract_info(url=url, download=False)
        except Exception as e:
            raise RuntimeError(f"Failed to enumerate playlist '{url}': {e}") from e

    entries = info.get('entries') or []  # type: ignore[union-attr]
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
