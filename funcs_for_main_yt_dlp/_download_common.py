"""Shared state, dataclass, and helpers used by download_video and download_audio."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadOptions:
    """Common options for yt-dlp download operations."""

    ytdlp_exe: str | Path
    url: str
    has_chapters: bool
    split_chapters: bool
    is_it_playlist: bool
    show_progress: bool = False
    video_download_timeout: int | None = None
    custom_title: str | None = None
    custom_artist: str | None = None
    custom_album: str | None = None


class _ProgressLogState:
    initialized: bool = False


# Shared mutable object so the progress-log flag persists across
# video + audio downloads that happen in the same run.
progress_log_state = _ProgressLogState()


def _quote_if_needed(value: str) -> str:
    """Quote a string with double quotes if it contains whitespace and isn't already quoted."""
    if ' ' in value or '\t' in value:
        # Check if already quoted
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value
        return f'"{value}"'
    return value


def _get_download_retries() -> str:
    """Get download retry count from YTDLP_RETRIES env var, defaulting to 100.

    Returns:
        Retry count as a string (positive integer, default '100')

    Raises:
        ValueError: If YTDLP_RETRIES is set but not a positive integer
    """
    retries = os.getenv('YTDLP_RETRIES', '').strip()
    if not retries:
        return '100'
    try:
        value = int(retries)
    except ValueError:
        raise ValueError(f"YTDLP_RETRIES must be a positive integer, got '{retries}'")
    if value <= 0:
        raise ValueError(f"YTDLP_RETRIES must be a positive integer, got '{retries}'")
    return retries
