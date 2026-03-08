"""Shared state, dataclass, and helpers used by download_video and download_audio."""
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from funcs_utils import get_cookie_args, sanitize_string
from funcs_video_info import get_video_info
from project_defs import YT_DLP_IS_PLAYLIST_FLAG, YT_DLP_SPLIT_CHAPTERS_FLAG

logger = logging.getLogger(__name__)


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
        str: Retry count as a string (positive integer, default '100')

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


def _build_output_template(opts: DownloadOptions,
                           output_folder: Path | str) -> tuple[str, str | None]:
    """Build the yt-dlp output template and return (template, sanitized_title).

    For playlists, sanitized_title is None (yt-dlp handles naming).
    For single videos, sanitized_title is the sanitized custom or fetched title.
    """
    folder = Path(output_folder)
    if opts.is_it_playlist:
        return str(folder / '%(title)s.%(ext)s'), None

    if opts.custom_title:
        sanitized_title = sanitize_string(dirty_string=opts.custom_title)
        logger.debug(f"Using custom title: '{opts.custom_title}' -> '{sanitized_title}'")
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        logger.debug(f"Sanitized title: '{video_title}' -> '{sanitized_title}'")

    return str(folder / f'{sanitized_title}.%(ext)s'), sanitized_title


def _append_common_flags(cmd: list[str | Path], opts: DownloadOptions,
                         sanitized_title: str | None = None) -> None:
    """Insert shared conditional flags into a yt-dlp command list (mutates cmd).

    Handles: cookies, playlist flag, split-chapters + windows-filenames,
    progress, custom_title metadata replacement, custom_artist/album ffmpeg metadata.
    """
    cookie_args = get_cookie_args()
    if cookie_args:
        cmd[1:1] = cookie_args

    if opts.is_it_playlist:
        cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]

    if opts.split_chapters and opts.has_chapters:
        cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
        # Chapter titles often contain ':' which is invalid on NTFS (/mnt/c/)
        cmd[1:1] = ['--windows-filenames']

    if opts.show_progress:
        cmd[1:1] = ['--progress']

    if opts.custom_title and sanitized_title:
        # Set the title metadata tag to the custom title
        cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]

    if opts.custom_artist or opts.custom_album:
        # Set metadata tags using ffmpeg postprocessor args
        ffmpeg_metadata: list[str] = []
        if opts.custom_artist:
            quoted_artist = _quote_if_needed(opts.custom_artist)
            ffmpeg_metadata.extend(['-metadata', f'artist={quoted_artist}',
                                    '-metadata', f'album_artist={quoted_artist}'])
        if opts.custom_album:
            quoted_album = _quote_if_needed(opts.custom_album)
            ffmpeg_metadata.extend(['-metadata', f'album={quoted_album}'])
        cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]


def _run_yt_dlp_subprocess(cmd: list[str | Path], timeout: int,
                           show_progress: bool, label: str, url: str) -> None:
    """Run a yt-dlp subprocess with optional progress logging.

    On success, logs completion. On error, propagates TimeoutExpired
    and CalledProcessError to the caller unchanged.
    """
    logger.info(f'Command: {cmd}')

    if show_progress:
        logs_dir = Path('Logs')
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / 'yt-dlp-progress.log'

        # First write overwrites, subsequent writes append
        mode = 'w' if not progress_log_state.initialized else 'a'
        progress_log_state.initialized = True

        with open(log_file, mode, encoding='utf-8') as f:
            _ = subprocess.run(cmd, check=True, stdout=f,
                               stderr=subprocess.PIPE, text=True, timeout=timeout)
        logger.info(f'{label} completed successfully. Progress logged to {log_file}')
        logger.info(f'Downloaded from URL: {url}')
    else:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
        logger.info(f'{label} completed successfully')
        logger.info(f'Downloaded from URL: {url}')
        if result.stdout:
            logger.debug(f'yt-dlp output: {result.stdout}')
