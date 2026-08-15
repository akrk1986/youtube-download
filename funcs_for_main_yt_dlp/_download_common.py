"""Shared state, dataclass, and helpers used by download_video and download_audio."""
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arrow

from funcs_utils import get_cookie_args, is_facebook_parse_error, sanitize_string
from funcs_video_info import get_video_info
from project_defs import YT_DLP_IS_PLAYLIST_FLAG

logger = logging.getLogger(__name__)

# Titles that identify no particular video. Facebook reports 'Video' for every clip, so naming
# the file after the title makes every Facebook download land on the same name.
GENERIC_VIDEO_TITLES = frozenset({'facebook', 'na', 'reel', 'untitled', 'video', 'videos', 'watch'})


@dataclass
class DownloadOptions:
    """Common options for yt-dlp download operations."""

    ytdlp_exe: str | Path
    url: str
    is_it_playlist: bool
    show_progress: bool = False
    video_download_timeout: int | None = None
    custom_title: str | None = None
    custom_artist: str | None = None
    custom_album: str | None = None


class _ProgressLogState:
    initialized: bool = False

    def reset(self) -> None:
        """Reset progress log state to uninitialized."""
        self.initialized = False


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
    except ValueError as exc:
        raise ValueError(f"YTDLP_RETRIES must be a positive integer, got '{retries}'") from exc
    if value <= 0:
        raise ValueError(f"YTDLP_RETRIES must be a positive integer, got '{retries}'")
    return retries


def _is_generic_title(title: str) -> bool:
    """Check whether a source title identifies no particular video (e.g. Facebook's 'Video')."""
    return title.strip().casefold() in GENERIC_VIDEO_TITLES


def _format_upload_date(upload_date: str) -> str:
    """Format a yt-dlp 'YYYYMMDD' upload date as 'YYYY-MM-DD' (empty when absent or unparsable)."""
    if not upload_date:
        return ''
    try:
        return arrow.get(upload_date, 'YYYYMMDD').format('YYYY-MM-DD')
    except ValueError:  # arrow's ParserError subclasses ValueError
        logger.debug(f"Could not parse upload date '{upload_date}'")
        return ''


def _name_for_generic_title(video_info: dict[str, Any], video_title: str) -> str:
    """Build a file name for a video whose own title identifies nothing.

    Uses '<uploader> <upload date>', falling back to the original title when the uploader is
    missing, and dropping the date when it is absent or unparsable.
    """
    uploader = (video_info.get('uploader') or '').strip()
    if uploader in ('', 'NA'):
        uploader = video_title.strip()
    upload_date = _format_upload_date(upload_date=(video_info.get('upload_date') or '').strip())
    return ' '.join(part for part in (uploader, upload_date) if part)


def _stem_exists(folder: Path, stem: str) -> bool:
    """Check whether the folder already holds a file with this base name, in any extension.

    The comparison is case-insensitive, so it also catches the Windows / mounted-drive case
    where 'Video.m4a' and 'video.m4a' are one and the same file.
    """
    if not folder.is_dir():
        return False
    target = stem.casefold()
    return any(entry.is_file() and entry.stem.casefold() == target for entry in folder.iterdir())


def _unique_output_stem(folder: Path, stem: str, video_id: str | None) -> str:
    """Return a base name that no file already in the folder uses.

    yt-dlp does not overwrite an existing target: it keeps the old media and writes the new
    video's tags and cover art onto it, yielding a file whose audio and artwork come from two
    different videos. Disambiguating the name up front avoids that.

    Appending the video id suffices on its own -- it is unique per video, so re-downloading the
    same video reuses that name and yt-dlp's own skip keeps the run idempotent. The numeric
    suffix is only for sources that report no id.
    """
    if not _stem_exists(folder=folder, stem=stem):
        return stem
    if video_id:
        return f'{stem} {video_id}'
    index = 2
    while _stem_exists(folder=folder, stem=f'{stem}-{index}'):
        index += 1
    return f'{stem}-{index}'


def _build_output_template(opts: DownloadOptions,
                           output_folder: Path | str) -> tuple[str, str | None]:
    """Build the yt-dlp output template and return (template, sanitized_title).

    For playlists, sanitized_title is None (yt-dlp handles naming).
    For single videos, sanitized_title is the sanitized custom or fetched title. The file name in
    the template can differ from it: a title that identifies no particular video is replaced, and
    a name already taken in the output folder is disambiguated.
    """
    folder = Path(output_folder)
    if opts.is_it_playlist:
        return str(folder / '%(title)s.%(ext)s'), None

    video_id: str | None = None
    if opts.custom_title:
        sanitized_title = sanitize_string(dirty_string=opts.custom_title)
        logger.debug(f"Using custom title: '{opts.custom_title}' -> '{sanitized_title}'")
        file_stem = sanitized_title
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        video_id = (video_info.get('id') or '').strip() or None
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        logger.debug(f"Sanitized title: '{video_title}' -> '{sanitized_title}'")
        file_stem = sanitized_title
        if _is_generic_title(title=video_title):
            fallback = sanitize_string(
                dirty_string=_name_for_generic_title(video_info=video_info, video_title=video_title)
            )
            if fallback:
                logger.info(f"Source title '{video_title}' identifies no particular video, "
                            f"naming the file '{fallback}' instead")
                file_stem = fallback

    file_stem = file_stem or 'untitled'
    unique_stem = _unique_output_stem(folder=folder, stem=file_stem, video_id=video_id)
    if unique_stem != file_stem:
        logger.info(f"'{file_stem}' is already taken in {folder}, "
                    f"downloading as '{unique_stem}' instead")
    return str(folder / f'{unique_stem}.%(ext)s'), sanitized_title


def _append_common_flags(cmd: list[str | Path], opts: DownloadOptions,
                         sanitized_title: str | None = None,
                         extra_ffmpeg_args: list[str] | None = None) -> None:
    """Insert shared conditional flags into a yt-dlp command list (mutates cmd).

    Handles: cookies, playlist flag, progress, custom_title metadata replacement,
    custom_artist/album ffmpeg metadata.

    Any ``extra_ffmpeg_args`` are merged into the SAME generic ``ffmpeg:`` ``--postprocessor-args``
    entry as the custom artist/album metadata. yt-dlp keeps only the last ``--postprocessor-args``
    for a given postprocessor key, so emitting a second ``ffmpeg:...`` elsewhere would silently
    drop the metadata — which is exactly why custom artist/album vanished from the M4A (it adds
    ``-movflags +faststart``) while the MP4 kept them. Callers pass such extras here instead.
    """
    cookie_args = get_cookie_args()
    if cookie_args:
        cmd[1:1] = cookie_args

    if opts.is_it_playlist:
        cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]

    if opts.show_progress:
        cmd[1:1] = ['--progress']

    if opts.custom_title and sanitized_title:
        # Set the title metadata tag to the custom title
        cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]

    # Build a single generic 'ffmpeg:' postprocessor-args entry combining custom artist/album
    # metadata and any caller-supplied extras (e.g. M4A faststart), so they never overwrite.
    ffmpeg_metadata: list[str] = []
    if opts.custom_artist:
        # Album Artist is intentionally not set -- it's reserved for the dupe
        # staging workflow (see README-Dupes.md).
        quoted_artist = _quote_if_needed(opts.custom_artist)
        ffmpeg_metadata.extend(['-metadata', f'artist={quoted_artist}'])
    if opts.custom_album:
        quoted_album = _quote_if_needed(opts.custom_album)
        ffmpeg_metadata.extend(['-metadata', f'album={quoted_album}'])
    if extra_ffmpeg_args:
        ffmpeg_metadata.extend(extra_ffmpeg_args)
    if ffmpeg_metadata:
        cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]


def _remove_cookie_args(cmd: list[str | Path], cookie_args: list[str]) -> list[str | Path]:
    """Return a copy of cmd with the contiguous cookie-args block removed (unchanged copy if absent)."""
    block_len = len(cookie_args)
    for i in range(len(cmd) - block_len + 1):
        if list(cmd[i:i + block_len]) == cookie_args:
            return list(cmd[:i]) + list(cmd[i + block_len:])
    return list(cmd)


def _run_yt_dlp_subprocess(cmd: list[str | Path], timeout: int,
                           show_progress: bool, label: str, url: str) -> None:
    """Run a yt-dlp subprocess, retrying once without browser cookies on a Facebook parse failure.

    Logged-in Facebook serves a page variant (e.g. the group-post view) that some yt-dlp versions
    fail on with 'Cannot parse data', while the same URL works anonymously. Other errors propagate
    to the caller unchanged (TimeoutExpired, CalledProcessError).
    """
    try:
        _run_yt_dlp_once(cmd=cmd, timeout=timeout, show_progress=show_progress, label=label, url=url)
    except subprocess.CalledProcessError as e:
        cookie_args = get_cookie_args()
        if not (cookie_args and is_facebook_parse_error(url=url, error_text=e.stderr)):
            raise
        cmd_no_cookies = _remove_cookie_args(cmd=cmd, cookie_args=cookie_args)
        if cmd_no_cookies == list(cmd):
            raise
        logger.warning(f"{label} failed with browser cookies ('Cannot parse data'), "
                       'retrying without cookies')
        _run_yt_dlp_once(cmd=cmd_no_cookies, timeout=timeout, show_progress=show_progress,
                         label=label, url=url)


def _run_yt_dlp_once(cmd: list[str | Path], timeout: int,
                     show_progress: bool, label: str, url: str) -> None:
    """Run a single yt-dlp subprocess attempt with optional progress logging.

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

        with log_file.open(mode, encoding='utf-8') as f:
            _ = subprocess.run(cmd, check=True, stdout=f,  # nosec B603
                               stderr=subprocess.PIPE, text=True, encoding='utf-8',
                               errors='replace', timeout=timeout)
        logger.info(f'{label} completed successfully. Progress logged to {log_file}')
        logger.info(f'Downloaded from URL: {url}')
    else:
        result = subprocess.run(  # nosec B603
            cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout
        )
        logger.info(f'{label} completed successfully')
        logger.info(f'Downloaded from URL: {url}')
        if result.stdout:
            logger.debug(f'yt-dlp output: {result.stdout}')
