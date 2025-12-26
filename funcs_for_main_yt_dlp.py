"""Helper functions for main-yt-dlp.py to reduce main() complexity."""
import logging
import sys
import platform
from pathlib import Path
import subprocess

from funcs_process_mp3_tags import set_artists_in_mp3_files, set_tags_in_chapter_mp3_files
from funcs_process_m4a_tags import set_artists_in_m4a_files, set_tags_in_chapter_m4a_files
from funcs_process_flac_tags import set_artists_in_flac_files, set_tags_in_chapter_flac_files
from funcs_utils import organize_media_files, sanitize_filenames_in_folder
from funcs_video_info import validate_video_url
from project_defs import MAX_URL_RETRIES, AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_M4A, AUDIO_OUTPUT_DIR_FLAC

logger = logging.getLogger(__name__)


def _get_audio_dir_for_format(audio_format: str) -> str:
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
    else:
        raise ValueError(f'Unknown audio format: {audio_format}')


def validate_and_get_url(provided_url: str) -> str | None:
    """
    Validate YouTube URL or prompt user for one if not provided.

    Args:
        provided_url: URL from command line, or None for interactive mode

    Returns:
        Validated YouTube URL

    Raises:
        SystemExit: If URL validation fails after max retries
    """
    if not provided_url:
        # Interactive mode: prompt with retry
        for attempt in range(MAX_URL_RETRIES):
            url = input('Enter the YouTube URL: ').strip()
            is_valid, error_msg = validate_video_url(url=url)
            if is_valid:
                return url

            logger.error(f'Invalid URL: {error_msg}')
            if attempt < MAX_URL_RETRIES - 1:
                logger.info(f'Please try again ({MAX_URL_RETRIES - attempt - 1} attempts remaining)')
            else:
                logger.error('Maximum retry attempts reached. Exiting.')
                sys.exit(1)
    else:
        # CLI mode: validate provided URL
        is_valid, error_msg = validate_video_url(url=provided_url)
        if not is_valid:
            logger.error(f'Invalid URL: {error_msg}')
            sys.exit(1)
        return provided_url


def organize_and_sanitize_files(video_folder: Path, audio_formats: list[str],
                                has_chapters: bool, only_audio: bool, need_audio: bool) -> dict[str, dict[str, str]]:
    """
    Organize chapter files and sanitize all downloaded file names.

    Args:
        video_folder: Path to video output directory
        audio_formats: List of audio formats (e.g., ['mp3', 'm4a', 'flac'])
        has_chapters: Whether video has chapters
        only_audio: Whether to skip video processing
        need_audio: Whether audio was downloaded

    Returns:
        dict with 'mp3', 'm4a', and 'flac' keys, each containing a mapping of final_path -> original_ytdlp_filename
    """
    original_names_mp3 = {}
    original_names_m4a = {}
    original_names_flac = {}

    # If chapters, move chapter files to their respective directories
    if has_chapters:
        result = organize_media_files(video_dir=video_folder)

        # Check move results
        if result['mp3'] or result['m4a'] or result['flac'] or result['mp4']:
            logger.info('Files organized successfully!')
        else:
            logger.warning('No MP3/M4A/FLAC or MP4 files found in current directory.')

        if result['errors']:
            logger.error('Errors encountered:')
            for error in result['errors']:
                logger.error(f'- {error}')

        # Extract original names for MP3, M4A, and FLAC files
        for path, orig_name in result.get('original_names', {}).items():
            if path.endswith('.mp3') or path.endswith('.MP3'):
                original_names_mp3[path] = orig_name
            elif path.endswith('.m4a') or path.endswith('.M4A'):
                original_names_m4a[path] = orig_name
            elif path.endswith('.flac') or path.endswith('.FLAC'):
                original_names_flac[path] = orig_name

    # Sanitize downloaded video file names
    if not only_audio:
        sanitize_filenames_in_folder(folder_path=video_folder)

    # Sanitize downloaded audio file names in their respective directories for each format
    if need_audio:
        for audio_format in audio_formats:
            audio_dir = Path(_get_audio_dir_for_format(audio_format=audio_format))
            if audio_dir.exists():
                if audio_format == 'mp3':
                    original_names_mp3 = sanitize_filenames_in_folder(folder_path=audio_dir,
                                                                      original_names=original_names_mp3)
                elif audio_format == 'm4a':
                    original_names_m4a = sanitize_filenames_in_folder(folder_path=audio_dir,
                                                                      original_names=original_names_m4a)
                elif audio_format == 'flac':
                    original_names_flac = sanitize_filenames_in_folder(folder_path=audio_dir,
                                                                       original_names=original_names_flac)

    return {'mp3': original_names_mp3, 'm4a': original_names_m4a, 'flac': original_names_flac}


def process_audio_tags(audio_formats: list[str], artists_json: Path,
                       has_chapters: bool, uploader_name: str | None, video_title: str | None,
                       original_names: dict[str, dict[str, str]] | None = None) -> None:
    """
    Process audio file tags based on formats.

    Args:
        audio_formats: List of audio formats (e.g., ['mp3', 'm4a', 'flac'])
        artists_json: Path to artists database JSON file
        has_chapters: Whether video has chapters
        uploader_name: Video uploader name (for chapter processing)
        video_title: Video title (for chapter processing)
        original_names: Optional dict with 'mp3', 'm4a', and 'flac' keys containing mappings of
                        final_path -> original_ytdlp_filename
    """
    if original_names is None:
        original_names = {'mp3': {}, 'm4a': {}, 'flac': {}}

    # Process each audio format
    for audio_format in audio_formats:
        if len(audio_formats) > 1:
            logger.info(f'Processing {audio_format.upper()} files...')

        audio_dir = Path(_get_audio_dir_for_format(audio_format=audio_format))

        if audio_format == 'mp3':
            set_artists_in_mp3_files(mp3_folder=audio_dir, artists_json=artists_json,
                                     original_names=original_names.get('mp3', {}))
            if has_chapters:
                _ = set_tags_in_chapter_mp3_files(mp3_folder=audio_dir, uploader=uploader_name,
                                                  video_title=video_title, original_names=original_names.get('mp3', {}))
        elif audio_format == 'm4a':
            set_artists_in_m4a_files(m4a_folder=audio_dir, artists_json=artists_json,
                                     original_names=original_names.get('m4a', {}))
            if has_chapters:
                _ = set_tags_in_chapter_m4a_files(m4a_folder=audio_dir, uploader=uploader_name,
                                                  video_title=video_title, original_names=original_names.get('m4a', {}))
        elif audio_format == 'flac':
            set_artists_in_flac_files(flac_folder=audio_dir, artists_json=artists_json,
                                      original_names=original_names.get('flac', {}))
            if has_chapters:
                _ = set_tags_in_chapter_flac_files(flac_folder=audio_dir, uploader=uploader_name,
                                                   video_title=video_title,
                                                   original_names=original_names.get('flac', {}))


def _get_external_paths() -> tuple[str, str, str]:
    """
    Determine yt-dlp, ffmpeg and ffprobe paths based on the operating system.

    Returns:
        tuple: Tuple of (yt_dlp_path, ffmpeg_path, ffprobe_path).
    """
    system = platform.system()

    if system == 'Windows':
        # Windows: use specific directory
        yt_dlp_dir = Path('C:/Users/user/Apps/yt-dlp')
        return str(yt_dlp_dir / 'ffmpeg.exe'), str(yt_dlp_dir / 'ffprobe.exe'), str(yt_dlp_dir / 'yt-dlp.exe')
    # Linux/WSL/macOS: assume ffmpeg/ffprobe are in PATH
    return 'ffmpeg', 'ffprobe', 'yt-dlp'


def get_ffmpeg_path() -> str:
    """
    Determine ffmpeg path based on the operating system.

    Returns:
        str: Path to ffmpeg executable.
    """
    ffmpeg_path, _, _ = _get_external_paths()

    # Windows
    if platform.system() == 'Windows':
        if Path(ffmpeg_path).exists():
            return ffmpeg_path
        logger.error(f"ffmpeg executable not found at path '{ffmpeg_path}'")
        logger.error(f"Please ensure ffmpeg is installed in '{ffmpeg_path}'")
        sys.exit(1)

    # Linux/WSL
    try:
        subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
        return ffmpeg_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'ffmpeg not found in PATH: {e}')
        logger.error("Install with: 'sudo apt install ffmpeg'")
        sys.exit(1)


def get_ytdlp_path() -> str:
    """
    Determine yt-dlp path based on the operating system.

    Returns:
        str: Path to yt-dlp executable.
    """
    _, _, yt_dlp_path = _get_external_paths()

    # Windows
    if platform.system() == 'Windows':
        if Path(yt_dlp_path).exists():
            return yt_dlp_path
        logger.error(f"yt-dlp executable not found at path '{yt_dlp_path}'")
        logger.error(f"Please ensure yt-dlp is installed in '{yt_dlp_path}'")
        sys.exit(1)

    # Linux/WSL
    try:
        subprocess.run([yt_dlp_path, '--version'], capture_output=True, check=True)
        return yt_dlp_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'yt-dlp not found in PATH: {e}')
        logger.error('Install with: pip install yt-dlp')
        sys.exit(1)


def quote_if_needed(value: str) -> str:
    """Quote a string with double quotes if it contains whitespace and isn't already quoted."""
    if ' ' in value or '\t' in value:
        # Check if already quoted
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value
        return f'"{value}"'
    return value
