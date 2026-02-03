"""Video metadata retrieval using yt-dlp."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yt_dlp

from funcs_utils import (get_cookie_args, is_format_error,
                         sanitize_url_for_subprocess)
from funcs_video_info.url_validation import get_timeout_for_url

logger = logging.getLogger(__name__)


class _SilentLogger:
    """Custom logger for yt-dlp that suppresses format errors."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        # Suppress format errors, log others at debug level
        if not is_format_error(msg):
            logger.debug(f'yt-dlp error: {msg}')


def get_video_info(yt_dlp_path: Path, url: str) -> dict:
    """Get video information using yt-dlp by requesting the meta-data as JSON, w/o download of the video."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=url)

    cmd = [
        str(yt_dlp_path),
        '--no-warnings',
        '--ignore-config',
        '--dump-json',
        '--no-download',
        sanitized_url
    ]

    # Add cookie arguments if configured via environment variable
    cookie_args = get_cookie_args()
    if cookie_args:
        cmd[1:1] = cookie_args

    logger.debug(f'Getting video info with timeout of {timeout} seconds')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)

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
            # Re-raise if it's not an "Extra data" error or no valid JSON found
            raise

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {timeout} seconds for URL '{url}'")
    except subprocess.CalledProcessError as e:
        # Check if this is a format error - return empty dict instead of raising
        if is_format_error(e.stderr):
            logger.debug(f'Format not available for URL, returning empty info: {url}')
            return {}
        raise RuntimeError(f'yt-dlp failed: {e.stderr}')
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse yt-dlp output for '{url}': {e}")


def is_playlist(url: str) -> bool:
    """Check if url is a playlist, w/o downloading.
    Using the yt-dlp Python library."""
    ydl_opts: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': _SilentLogger(),
    }

    # Add cookie configuration if environment variable is set
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if cookie_env:
        browser = 'chrome' if cookie_env.lower() == 'chrome' else 'firefox'
        ydl_opts['cookiesfrombrowser'] = (browser,)

    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:  # type: ignore[arg-type]
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
