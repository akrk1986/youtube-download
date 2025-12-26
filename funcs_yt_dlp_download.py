"""Download functions for yt-dlp operations."""
import logging
import os
import subprocess
from pathlib import Path

from funcs_utils import (get_cookie_args, get_timeout_for_url, get_video_info,
                         sanitize_string, sanitize_url_for_subprocess)
from project_defs import (AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_FLAC, AUDIO_OUTPUT_DIR_M4A,
                          DEFAULT_AUDIO_QUALITY,
                          YT_DLP_IS_PLAYLIST_FLAG, YT_DLP_SPLIT_CHAPTERS_FLAG, YT_DLP_WRITE_JSON_FLAG)

logger = logging.getLogger(__name__)

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


def run_yt_dlp(ytdlp_exe: Path, video_url: str, video_folder: str, get_subs: bool,
               write_json: bool, has_chapters: bool, split_chapters: bool, is_it_playlist: bool,
               show_progress: bool = False, video_download_timeout: int | None = None,
               custom_title: str | None = None, custom_artist: str | None = None,
               custom_album: str | None = None) -> None:
    """Extract videos from video URL with yt-dlp. Include subtitles if requested."""
    global _progress_log_initialized

    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=video_url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=video_url, video_download_timeout=video_download_timeout)

    # Determine output filename template
    # For single videos, use custom title if provided, otherwise get and sanitize the video title
    # For playlists, use yt-dlp template
    if is_it_playlist:
        output_template = os.path.join(video_folder, '%(title)s.%(ext)s')
    elif custom_title:
        sanitized_title = sanitize_string(dirty_string=custom_title)
        output_template = os.path.join(video_folder, f'{sanitized_title}.%(ext)s')
        logger.debug(f"Using custom title: '{custom_title}' -> '{sanitized_title}'")
    else:
        video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=video_url)
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        output_template = os.path.join(video_folder, f'{sanitized_title}.%(ext)s')
        logger.debug(f"Sanitized video title: '{video_title}' -> '{sanitized_title}'")

    yt_dlp_cmd = [
        ytdlp_exe,
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
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
        yt_dlp_cmd[1:1] = cookie_args

    if is_it_playlist:
        yt_dlp_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if write_json:
        yt_dlp_cmd[1:1] = [YT_DLP_WRITE_JSON_FLAG]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
        # Remux to MP4 after splitting to fix container metadata and ensure proper seeking
        yt_dlp_cmd[1:1] = ['--remux-video', 'mp4']
    if get_subs:
        # Extract subtitles in Greek, English, Hebrew
        yt_dlp_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    if show_progress:
        yt_dlp_cmd[1:1] = ['--progress']
    if custom_title:
        # Set the title metadata tag to the custom title
        yt_dlp_cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]
    if custom_artist or custom_album:
        # Set metadata tags using ffmpeg postprocessor args
        ffmpeg_metadata = []
        if custom_artist:
            quoted_artist = _quote_if_needed(custom_artist)
            ffmpeg_metadata.extend(['-metadata', f'artist={quoted_artist}',
                                    '-metadata', f'album_artist={quoted_artist}'])
        if custom_album:
            quoted_album = _quote_if_needed(custom_album)
            ffmpeg_metadata.extend(['-metadata', f'album={quoted_album}'])
        yt_dlp_cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]

    logger.info(f'Downloading media, using timeout of {timeout} seconds for video download')
    logger.info(f'Command: {yt_dlp_cmd}')

    # Run download with error handling
    # Note: Some videos in playlists may be unavailable, which is expected
    try:
        if show_progress:
            # Create Logs directory if it doesn't exist, set up log file for download progress (very verbose)
            logs_dir = Path('Logs')
            logs_dir.mkdir(exist_ok=True)
            log_file = logs_dir / 'yt-dlp-progress.log'

            # First write overwrites, subsequent writes append
            mode = 'w' if not _progress_log_initialized else 'a'
            _progress_log_initialized = True

            with open(log_file, mode) as f:
                result = subprocess.run(yt_dlp_cmd, check=True, stdout=f, stderr=subprocess.STDOUT,
                                        text=True, timeout=timeout)
            logger.info(f'Video download completed successfully. Progress logged to {log_file}')
            logger.info(f'Downloaded from URL: {video_url}')
        else:
            result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
            logger.info('Video download completed successfully')
            logger.info(f'Downloaded from URL: {video_url}')
            if result.stdout:
                logger.debug(f'yt-dlp output: {result.stdout}')
    except subprocess.TimeoutExpired:
        logger.error(f"Video download timed out after {timeout} seconds for URL '{video_url}'")
        if not is_it_playlist:
            raise RuntimeError(f"Download timed out for '{video_url}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"Video download failed for URL '{video_url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        # For playlists, partial failure is acceptable
        if is_it_playlist:
            logger.warning(f"Some videos in playlist '{video_url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download video from '{video_url}': {e.stderr}")


def extract_single_format(ytdlp_exe: Path, video_url: str, output_folder: str,
                          has_chapters: bool, split_chapters: bool, is_it_playlist: bool,
                          format_type: str, artist_pat: str | None = None,
                          album_artist_pat: str | None = None,
                          show_progress: bool = False, video_download_timeout: int | None = None,
                          custom_title: str | None = None, custom_artist: str | None = None,
                          custom_album: str | None = None) -> None:
    """Extract audio in a single format using yt-dlp."""
    global _progress_log_initialized

    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=video_url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=video_url, video_download_timeout=video_download_timeout)

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # For FLAC (lossless), use best quality (0); for lossy formats use default quality
    audio_quality = '0' if format_type == 'flac' else DEFAULT_AUDIO_QUALITY

    # Determine output filename template
    # For single videos, use custom title if provided, otherwise get and sanitize the video title
    # For playlists, use yt-dlp template
    if is_it_playlist:
        output_template = os.path.join(output_folder, '%(title)s.%(ext)s')
    elif custom_title:
        sanitized_title = sanitize_string(dirty_string=custom_title)
        output_template = os.path.join(output_folder, f'{sanitized_title}.%(ext)s')
        logger.debug(f"Using custom title: '{custom_title}' -> '{sanitized_title}'")
    else:
        video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=video_url)
        video_title = video_info.get('title', 'untitled')
        sanitized_title = sanitize_string(dirty_string=video_title)
        output_template = os.path.join(output_folder, f'{sanitized_title}.%(ext)s')
        logger.debug(f"Sanitized audio title: '{video_title}' -> '{sanitized_title}'")

    yt_dlp_cmd = [
        ytdlp_exe,
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

    if is_it_playlist:
        yt_dlp_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if artist_pat and album_artist_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', artist_pat,
                           '--parse-metadata', album_artist_pat,
                           ]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
    if show_progress:
        yt_dlp_cmd[1:1] = ['--progress']
    if custom_title:
        # Set the title metadata tag to the custom title
        yt_dlp_cmd[1:1] = ['--replace-in-metadata', 'title', '.+', sanitized_title]
    if custom_artist or custom_album:
        # Set metadata tags using ffmpeg postprocessor args
        ffmpeg_metadata = []
        if custom_artist:
            quoted_artist = _quote_if_needed(custom_artist)
            ffmpeg_metadata.extend(['-metadata', f'artist={quoted_artist}',
                                    '-metadata', f'album_artist={quoted_artist}'])
        if custom_album:
            quoted_album = _quote_if_needed(custom_album)
            ffmpeg_metadata.extend(['-metadata', f'album={quoted_album}'])
        yt_dlp_cmd[1:1] = ['--postprocessor-args', 'ffmpeg:' + ' '.join(ffmpeg_metadata)]

    logger.info(f'Downloading and extracting {format_type.upper()} audio with yt-dlp')
    logger.info(f'Using timeout of {timeout} seconds for {format_type.upper()} audio download')
    logger.info(f'Command: {yt_dlp_cmd}')

    # Run download with error handling
    # Note: In playlists, some videos may be unavailable, which is not considered an error
    try:
        if show_progress:
            # Create Logs directory if it doesn't exist
            log_dir = Path('Logs')
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / 'yt-dlp-progress.log'

            # First write overwrites, subsequent writes append
            mode = 'w' if not _progress_log_initialized else 'a'
            _progress_log_initialized = True

            with open(log_file, mode) as f:
                result = subprocess.run(
                    yt_dlp_cmd, check=True, stdout=f,
                    stderr=subprocess.STDOUT, text=True, timeout=timeout)
            logger.info(f'{format_type.upper()} audio download completed successfully. Progress logged to {log_file}')
            logger.info(f'Downloaded from URL: {video_url}')
        else:
            result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
            logger.info(f'{format_type.upper()} audio download completed successfully')
            logger.info(f'Downloaded from URL: {video_url}')
            if result.stdout:
                logger.debug(f'yt-dlp output: {result.stdout}')
    except subprocess.TimeoutExpired:
        logger.error(f"{format_type.upper()} audio download timed out after {timeout} seconds for URL '{video_url}'")
        if not is_it_playlist:
            raise RuntimeError(f"Audio download timed out for '{video_url}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"{format_type.upper()} audio download failed for URL '{video_url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        # For playlists, partial failure is acceptable
        if is_it_playlist:
            logger.warning(f"Some videos in playlist '{video_url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download {format_type.upper()} audio from '{video_url}': {e.stderr}")


def extract_audio_with_ytdlp(ytdlp_exe: Path, playlist_url: str,
                             has_chapters: bool, split_chapters: bool, is_it_playlist: bool,
                             audio_formats: list[str], show_progress: bool = False,
                             video_download_timeout: int | None = None,
                             custom_title: str | None = None, custom_artist: str | None = None,
                             custom_album: str | None = None) -> None:
    """Use yt-dlp to download and extract audio with metadata and thumbnail."""

    # For a single video, check if video has 'artist' or 'uploader' tags.
    # Use either to embed 'artist' and 'albumartist' tags in the audio file.
    artist_pat = album_artist_pat = None

    if is_it_playlist:
        have_artist = have_uploader = False
        logger.info('URL is a playlist, cannot extract artist/uploader')
    else:
        video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=playlist_url)
        artist = video_info.get('artist')
        uploader = video_info.get('uploader')
        have_artist = artist and artist not in ('NA', '')
        have_uploader = uploader and uploader not in ('NA', '')

        if have_artist:
            artist_pat = 'artist:%(artist)s'
            album_artist_pat = 'album_artist:%(artist)s'
            logger.info(f"Video has artist: '{artist}'")
        elif have_uploader:
            artist_pat = 'artist:%(uploader)s'
            album_artist_pat = 'album_artist:%(uploader)s'
            logger.info(f"Video has uploader: '{uploader}'")

    # Extract each requested audio format
    timeout = get_timeout_for_url(url=playlist_url, video_download_timeout=video_download_timeout)
    logger.info(f'Using timeout of {timeout} seconds for audio extraction')
    for audio_format in audio_formats:
        # Get the appropriate output directory for this format
        output_dir = os.path.abspath(get_audio_dir_for_format(audio_format=audio_format))
        extract_single_format(ytdlp_exe=ytdlp_exe, video_url=playlist_url, output_folder=output_dir,
                              has_chapters=has_chapters,
                              split_chapters=split_chapters, is_it_playlist=is_it_playlist, format_type=audio_format,
                              artist_pat=artist_pat, album_artist_pat=album_artist_pat,
                              show_progress=show_progress, video_download_timeout=video_download_timeout,
                              custom_title=custom_title, custom_artist=custom_artist,
                              custom_album=custom_album)
