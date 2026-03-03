"""Video download functions using yt-dlp."""
import logging
import subprocess
from pathlib import Path

from funcs_for_main_yt_dlp._download_common import (
    DownloadOptions,
    _append_common_flags,
    _build_output_template,
    _get_download_retries,
    _run_yt_dlp_subprocess,
)
from funcs_utils import is_format_error, sanitize_url_for_subprocess
from funcs_video_info import get_timeout_for_url
from project_defs import YT_DLP_WRITE_JSON_FLAG

logger = logging.getLogger(__name__)

# Format strings to try in order, from most preferred to most permissive
VIDEO_FORMAT_FALLBACKS = [
    'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',  # Preferred: MP4+M4A, then any
    'bv*+ba/b',  # Very permissive: any video + any audio, or best combined
]


def run_yt_dlp(opts: DownloadOptions, video_folder: Path | str, get_subs: bool, write_json: bool) -> None:
    """Extract videos from video URL with yt-dlp. Include subtitles if requested."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=opts.url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=opts.url, video_download_timeout=opts.video_download_timeout)

    output_template, sanitized_title = _build_output_template(opts=opts, output_folder=video_folder)

    # Build base command (format will be inserted during retry loop)
    format_placeholder = '__FORMAT__'
    download_retries = _get_download_retries()
    base_cmd: list[str | Path] = [
        opts.ytdlp_exe,
        '--no-warnings',  # Suppress yt-dlp warnings (format errors handled via retry)
        '--retries', download_retries,  # Retry on connection drops (default: 100)
        '-f', format_placeholder,  # Placeholder for format, will be set in loop
        '--merge-output-format', 'mp4',
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',  # Embed YouTube thumbnail as cover art in MP4
        '--parse-metadata', 'webpage_url:%(meta_comment)s',  # Store URL in comment metadata
        '-o', output_template,
        sanitized_url
    ]

    # Add shared flags (cookies, playlist, split-chapters, progress, custom metadata)
    _append_common_flags(cmd=base_cmd, opts=opts, sanitized_title=sanitized_title)

    # Add video-specific flags
    if write_json:
        base_cmd[1:1] = [YT_DLP_WRITE_JSON_FLAG]
    if get_subs:
        # Extract subtitles in Greek, English, Hebrew
        base_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]

    # Find the index of the format placeholder (after -f flag)
    format_index = base_cmd.index(format_placeholder)

    logger.info(f'Downloading media, using timeout of {timeout} seconds for video download')

    # Try each format in sequence until one succeeds
    last_error = None
    for format_str in VIDEO_FORMAT_FALLBACKS:
        yt_dlp_cmd = base_cmd.copy()
        yt_dlp_cmd[format_index] = format_str

        logger.debug(f'Trying format: {format_str}')

        try:
            _run_yt_dlp_subprocess(cmd=yt_dlp_cmd, timeout=timeout,
                                   show_progress=opts.show_progress,
                                   label='Video download', url=opts.url)
            return  # Success, exit function

        except subprocess.TimeoutExpired:
            logger.error(f"Video download timed out after {timeout} seconds for URL '{opts.url}'")
            if not opts.is_it_playlist:
                raise RuntimeError(f"Download timed out for '{opts.url}'")
            return

        except subprocess.CalledProcessError as e:
            last_error = e
            # Check stderr for format error (also check stdout in case messages went there)
            error_output = (e.stderr or '') + (e.stdout or '')
            if is_format_error(error_output):
                logger.debug(f'Format {format_str} not available, trying next format...')
                continue

            # Non-format error, handle normally
            logger.error(f"Video download failed for URL '{opts.url}' (exit code {e.returncode})")
            if e.stderr:
                logger.error(f'Error details: {e.stderr}')
            if opts.is_it_playlist:
                logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
                return
            raise RuntimeError(f"Failed to download video from '{opts.url}': {e.stderr}")

    # All formats failed
    logger.error(f"All format options exhausted for URL '{opts.url}'")
    if opts.is_it_playlist:
        logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
    else:
        stderr = last_error.stderr if last_error else 'Unknown error'
        raise RuntimeError(f"No compatible format found for '{opts.url}': {stderr}")
