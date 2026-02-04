"""Download functions for yt-dlp operations."""
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from funcs_utils import (get_cookie_args, is_format_error, sanitize_string,
                         sanitize_url_for_subprocess)
from funcs_video_info import get_timeout_for_url, get_video_info
from project_defs import (AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_FLAC,
                          AUDIO_OUTPUT_DIR_M4A, DEFAULT_AUDIO_QUALITY,
                          FFMPEG_TIMEOUT_SECONDS, GLOB_MP4_FILES,
                          YT_DLP_IS_PLAYLIST_FLAG, YT_DLP_SPLIT_CHAPTERS_FLAG,
                          YT_DLP_WRITE_JSON_FLAG)

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


# Track if progress log file has been initialized (for --progress flag)
_progress_log_initialized = False


def get_audio_dir_for_format(audio_format: str) -> str:
    """
    Get the output directory for a given audio format.

    Args:
        audio_format: Audio format ('mp3', 'm4a', or 'flac')

    Returns:
        Directory path for the format
    """
    if audio_format == 'mp3':
        return AUDIO_OUTPUT_DIR
    elif audio_format == 'm4a':
        return AUDIO_OUTPUT_DIR_M4A
    elif audio_format == 'flac':
        return AUDIO_OUTPUT_DIR_FLAC
    raise ValueError(f'Unknown audio format: {audio_format}')


def _quote_if_needed(value: str) -> str:
    """Quote a string with double quotes if it contains whitespace and isn't already quoted."""
    if ' ' in value or '\t' in value:
        # Check if already quoted
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value
        return f'"{value}"'
    return value


# Format strings to try in order, from most preferred to most permissive
VIDEO_FORMAT_FALLBACKS = [
    'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',  # Preferred: MP4+M4A, then any
    'bv*+ba/b',  # Very permissive: any video + any audio, or best combined
]

# Matches yt-dlp chapter filenames: '<title> - NNN <chapter_title>'
_VIDEO_CHAPTER_PATTERN = re.compile(r'^.*?\s*-\s*(\d{3})\s+.+')


def run_yt_dlp(opts: DownloadOptions, video_folder: Path | str, get_subs: bool, write_json: bool) -> None:
    """Extract videos from video URL with yt-dlp. Include subtitles if requested."""
    global _progress_log_initialized

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
    base_cmd: list[str | Path] = [
        opts.ytdlp_exe,
        '--no-warnings',  # Suppress yt-dlp warnings (format errors handled via retry)
        '-f', format_placeholder,  # Placeholder for format, will be set in loop
        '--merge-output-format', 'mp4',
        '--embed-metadata',
        '--add-metadata',
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
                mode = 'w' if not _progress_log_initialized else 'a'
                _progress_log_initialized = True

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


def remux_video_chapters(ffmpeg_path: str, video_folder: Path,
                         chapters: list[dict] | None = None) -> None:
    """Remux split video chapter files to fix duration metadata and set chapter titles.

    yt-dlp's --split-chapters creates MP4 files whose container duration
    still reflects the original (full) video. A stream-copy remux via ffmpeg
    rewrites the container with the correct duration. If chapters metadata is
    provided, also sets the title tag to the individual chapter title.
    """
    # Chapter files may land in CWD or in video_folder depending on yt-dlp version
    candidates = list(Path.cwd().glob(GLOB_MP4_FILES)) + list(video_folder.glob(GLOB_MP4_FILES))
    # Deduplicate resolved paths (handles CWD == video_folder)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in candidates:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)

    # Filter to chapter files only (stem matches ' - NNN ' pattern)
    chapter_files = [f for f in unique if _VIDEO_CHAPTER_PATTERN.match(f.stem)]

    if not chapter_files:
        logger.debug('No video chapter files to remux')
        return

    logger.info(f'Remuxing {len(chapter_files)} video chapter file(s) to fix duration metadata')

    for mp4_file in chapter_files:
        temp_file = mp4_file.with_name(mp4_file.stem + '.remux.mp4')

        # Set title and trim to chapter duration if chapters info is available
        metadata_args: list[str] = []
        duration_args: list[str] = []
        match = _VIDEO_CHAPTER_PATTERN.match(mp4_file.stem)
        if match and chapters:
            chapter_num = int(match.group(1))
            if 1 <= chapter_num <= len(chapters):
                chapter = chapters[chapter_num - 1]
                chapter_title = chapter.get('title', '')
                if chapter_title:
                    metadata_args = ['-metadata', f'title={chapter_title}']
                start_time = chapter.get('start_time', 0)
                end_time = chapter.get('end_time', 0)
                if end_time > start_time:
                    duration_args = ['-t', str(end_time - start_time)]

        try:
            cmd = [ffmpeg_path, '-y', '-i', str(mp4_file), '-c', 'copy'] + duration_args + metadata_args + [str(temp_file)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT_SECONDS,
                           encoding='utf-8', errors='replace')
            temp_file.replace(mp4_file)
            logger.info(f"Remuxed '{mp4_file.name}'")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remux '{mp4_file.name}': {e.stderr}")
            if temp_file.exists():
                temp_file.unlink()
        except subprocess.TimeoutExpired:
            logger.error(f"Remux timed out for '{mp4_file.name}'")
            if temp_file.exists():
                temp_file.unlink()


def extract_single_format(opts: DownloadOptions, output_folder: Path | str, format_type: str,
                          artist_pat: str | None = None,
                          album_artist_pat: str | None = None) -> None:
    """Extract audio in a single format using yt-dlp."""
    global _progress_log_initialized

    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=opts.url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=opts.url, video_download_timeout=opts.video_download_timeout)

    # Ensure output folder exists
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    # For FLAC (lossless), use best quality (0); for lossy formats use default quality
    audio_quality = '0' if format_type == 'flac' else DEFAULT_AUDIO_QUALITY

    # Determine output filename template
    # For single videos, use custom title if provided, otherwise get and sanitize the video title
    # For playlists, use yt-dlp template
    if opts.is_it_playlist:
        output_template = str(output_folder_path / '%(title)s.%(ext)s')
    elif opts.custom_title:
        sanitized_title = sanitize_string(dirty_string=opts.custom_title)
        output_template = str(output_folder_path / f'{sanitized_title}.%(ext)s')
        logger.debug(f"Using custom title: '{opts.custom_title}' -> '{sanitized_title}'")
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        output_template = str(output_folder_path / f'{sanitized_title}.%(ext)s')
        logger.debug(f"Sanitized audio title: '{video_title}' -> '{sanitized_title}'")

    yt_dlp_cmd: list[str | Path] = [
        opts.ytdlp_exe,
        '--no-warnings',  # Suppress yt-dlp warnings (format errors handled via retry)
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', format_type,
        '--audio-quality', audio_quality,
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',
        '-o', output_template,
        sanitized_url
    ]

    # Add cookie arguments if configured via environment variable
    cookie_args = get_cookie_args()
    if cookie_args:
        yt_dlp_cmd[1:1] = cookie_args

    if opts.is_it_playlist:
        yt_dlp_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if artist_pat and album_artist_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', artist_pat,
                           '--parse-metadata', album_artist_pat,
                           ]
    if opts.split_chapters and opts.has_chapters:
        yt_dlp_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
        # Chapter titles often contain ':' which is invalid on NTFS (/mnt/c/)
        yt_dlp_cmd[1:1] = ['--windows-filenames']
    if opts.show_progress:
        yt_dlp_cmd[1:1] = ['--progress']
    if opts.custom_title:
        # Set the title metadata tag to the custom title
        yt_dlp_cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]
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
        yt_dlp_cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]

    logger.info(f'Downloading and extracting {format_type.upper()} audio with yt-dlp')
    logger.info(f'Using timeout of {timeout} seconds for {format_type.upper()} audio download')
    logger.info(f'Command: {yt_dlp_cmd}')

    # Run download with error handling
    # Note: In playlists, some videos may be unavailable, which is not considered an error
    try:
        if opts.show_progress:
            # Create Logs directory if it doesn't exist
            log_dir = Path('Logs')
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / 'yt-dlp-progress.log'

            # First write overwrites, subsequent writes append
            mode = 'w' if not _progress_log_initialized else 'a'
            _progress_log_initialized = True

            with open(log_file, mode, encoding='utf-8') as f:
                # Capture stderr separately to detect format errors
                _ = subprocess.run(
                    yt_dlp_cmd, check=True, stdout=f,
                    stderr=subprocess.PIPE, text=True, timeout=timeout)
            logger.info(f'{format_type.upper()} audio download completed successfully. Progress logged to {log_file}')
            logger.info(f'Downloaded from URL: {opts.url}')
        else:
            result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
            logger.info(f'{format_type.upper()} audio download completed successfully')
            logger.info(f'Downloaded from URL: {opts.url}')
            if result.stdout:
                logger.debug(f'yt-dlp output: {result.stdout}')
    except subprocess.TimeoutExpired:
        logger.error(f"{format_type.upper()} audio download timed out after {timeout} seconds for URL '{opts.url}'")
        if not opts.is_it_playlist:
            raise RuntimeError(f"Audio download timed out for '{opts.url}'")
    except subprocess.CalledProcessError as e:
        # Check if this is a format error - suppress it, only log non-format errors
        error_output = (e.stderr or '') + (e.stdout or '')
        if is_format_error(error_output):
            # Format error - the bestaudio/best fallback should have worked, but didn't
            # This is unusual, log at debug level and continue
            logger.debug(f'{format_type.upper()} format not available for this video')
            if opts.is_it_playlist:
                logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
            return  # Don't raise for format errors - the format simply isn't available
        # Non-format error
        logger.error(f"{format_type.upper()} audio download failed for URL '{opts.url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        if opts.is_it_playlist:
            logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download {format_type.upper()} audio from '{opts.url}': {e.stderr}")


def extract_audio_with_ytdlp(opts: DownloadOptions, audio_formats: list[str]) -> None:
    """Use yt-dlp to download and extract audio with metadata and thumbnail."""

    # For a single video, check if video has 'artist' or 'uploader' tags.
    # Use either to embed 'artist' and 'albumartist' tags in the audio file.
    artist_pat = album_artist_pat = None

    if opts.is_it_playlist:
        logger.info('URL is a playlist, cannot extract artist/uploader')
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        artist = video_info.get('artist')
        uploader = video_info.get('uploader')
        have_artist = bool(artist and artist not in ('NA', ''))
        have_uploader = bool(uploader and uploader not in ('NA', ''))

        if have_artist:
            artist_pat = 'artist:%(artist)s'
            album_artist_pat = 'album_artist:%(artist)s'
            logger.info(f"Video has artist: '{artist}'")
        elif have_uploader:
            artist_pat = 'artist:%(uploader)s'
            album_artist_pat = 'album_artist:%(uploader)s'
            logger.info(f"Video has uploader: '{uploader}'")

    # Extract each requested audio format
    timeout = get_timeout_for_url(url=opts.url, video_download_timeout=opts.video_download_timeout)
    logger.info(f'Using timeout of {timeout} seconds for audio extraction')
    for audio_format in audio_formats:
        # Get the appropriate output directory for this format
        output_dir = Path(get_audio_dir_for_format(audio_format=audio_format)).resolve()
        extract_single_format(opts=opts, output_folder=output_dir, format_type=audio_format,
                              artist_pat=artist_pat, album_artist_pat=album_artist_pat)
