"""File organization and sanitization utilities."""
import logging
from pathlib import Path

from funcs_utils import organize_media_files, sanitize_filenames_in_folder
from project_defs import AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_FLAC, AUDIO_OUTPUT_DIR_M4A

logger = logging.getLogger(__name__)


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


def organize_and_sanitize_files(video_folder: Path, audio_formats: list[str],
                                has_chapters: bool, only_audio: bool, need_audio: bool,
                                chapter_name_map: dict[int, str] | None = None) -> dict[str, dict[str, str]]:
    """
    Organize chapter files and sanitize all downloaded file names.

    Args:
        video_folder: Path to video output directory
        audio_formats: List of audio formats (e.g., ['mp3', 'm4a', 'flac'])
        has_chapters: Whether video has chapters
        only_audio: Whether to skip video processing
        need_audio: Whether audio was downloaded
        chapter_name_map: Optional mapping of chapter numbers to normalized filenames

    Returns:
        dict with 'mp3', 'm4a', and 'flac' keys, each containing a mapping of final_path -> original_ytdlp_filename
    """
    original_names_mp3 = {}
    original_names_m4a = {}
    original_names_flac = {}

    # If chapters, move chapter files to their respective directories
    if has_chapters:
        result = organize_media_files(video_dir=video_folder, chapter_name_map=chapter_name_map)

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
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
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


def count_files(directory: Path, extensions: list[str]) -> int:
    """Count files with specified extensions in a directory (including subdirectories)."""
    if not directory.exists():
        return 0

    count = 0
    for ext in extensions:
        # Count files with the extension (case-insensitive)
        count += len(list(directory.rglob(f'*{ext}')))
        count += len(list(directory.rglob(f'*{ext.upper()}')))
    return count
