"""Video download functions using yt-dlp."""
import logging
import subprocess
from pathlib import Path

from funcs_for_main_yt_dlp._download_common import (
    DownloadOptions,
    _get_download_retries,
    _quote_if_needed,
    progress_log_state,
)
from funcs_utils import (get_cookie_args, is_format_error, sanitize_string,
                         sanitize_url_for_subprocess)
from funcs_video_info import get_timeout_for_url, get_video_info
from project_defs import (YT_DLP_IS_PLAYLIST_FLAG, YT_DLP_SPLIT_CHAPTERS_FLAG,
                          YT_DLP_WRITE_JSON_FLAG)

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

    # Determine output filename template
    # For single videos, use custom title if provided, otherwise get and sanitize the video title
    # For playlists, use yt-dlp template
    video_folder_path = Path(video_folder)
    if opts.is_it_playlist:
        output_template = str(video_folder_path / '%(title)s.%(ext)s')
    elif opts.custom_title:
        sanitized_title = sanitize_string(dirty_string=opts.custom_title)
        output_template = str(video_folder_path / f'{sanitized_title}.%(ext)s')
        logger.debug(f"Using custom title: '{opts.custom_title}' -> '{sanitized_title}'")
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        output_template = str(video_folder_path / f'{sanitized_title}.%(ext)s')
        logger.debug(f"Sanitized video title: '{video_title}' -> '{sanitized_title}'")

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

    # Add cookie arguments if configured via environment variable
    cookie_args = get_cookie_args()
    if cookie_args:
        base_cmd[1:1] = cookie_args

    if opts.is_it_playlist:
        base_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if write_json:
        base_cmd[1:1] = [YT_DLP_WRITE_JSON_FLAG]
    if opts.split_chapters and opts.has_chapters:
        base_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
        # Chapter titles often contain ':' which is invalid on NTFS (/mnt/c/)
        base_cmd[1:1] = ['--windows-filenames']
    if get_subs:
        # Extract subtitles in Greek, English, Hebrew
        base_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    if opts.show_progress:
        base_cmd[1:1] = ['--progress']
    if opts.custom_title:
        # Set the title metadata tag to the custom title
        base_cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]
    if opts.custom_artist or opts.custom_album:
        # Set metadata tags using ffmpeg postprocessor args
        ffmpeg_metadata = []
        if opts.custom_artist:
            quoted_artist = _quote_if_needed(opts.custom_artist)
            ffmpeg_metadata.extend(['-metadata', f'artist={quoted_artist}',
                                    '-metadata', f'album_artist={quoted_artist}'])
        if opts.custom_album:
            quoted_album = _quote_if_needed(opts.custom_album)
            ffmpeg_metadata.extend(['-metadata', f'album={quoted_album}'])
        base_cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]

    # Find the index of the format placeholder (after -f flag)
    format_index = base_cmd.index(format_placeholder)

    logger.info(f'Downloading media, using timeout of {timeout} seconds for video download')

    # Try each format in sequence until one succeeds
    last_error = None
    for format_str in VIDEO_FORMAT_FALLBACKS:
        yt_dlp_cmd = base_cmd.copy()
        yt_dlp_cmd[format_index] = format_str

        logger.debug(f'Trying format: {format_str}')
        logger.info(f'Command: {yt_dlp_cmd}')

        try:
            if opts.show_progress:
                # Create Logs directory if it doesn't exist, set up log file for download progress (very verbose)
                logs_dir = Path('Logs')
                logs_dir.mkdir(exist_ok=True)
                log_file = logs_dir / 'yt-dlp-progress.log'

                # First write overwrites, subsequent writes append
                mode = 'w' if not progress_log_state.initialized else 'a'
                progress_log_state.initialized = True

                with open(log_file, mode, encoding='utf-8') as f:
                    # Capture stderr separately to detect format errors
                    _ = subprocess.run(yt_dlp_cmd, check=True, stdout=f,
                                       stderr=subprocess.PIPE, text=True, timeout=timeout)
                logger.info(f'Video download completed successfully. Progress logged to {log_file}')
                logger.info(f'Downloaded from URL: {opts.url}')
            else:
                result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
                logger.info('Video download completed successfully')
                logger.info(f'Downloaded from URL: {opts.url}')
                if result.stdout:
                    logger.debug(f'yt-dlp output: {result.stdout}')
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
