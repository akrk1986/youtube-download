"""File organization and sanitization utilities."""
import logging
from pathlib import Path

from funcs_utils import sanitize_filenames_in_folder
from project_defs import (AUDIO_OUTPUT_DIR_FLAC, AUDIO_OUTPUT_DIR_M4A,
                           AUDIO_OUTPUT_DIR_MP3, VIDEO_OUTPUT_DIR)

logger = logging.getLogger(__name__)


def get_audio_dir_for_format(audio_format: str) -> str:
    """
    Get the output directory for a given audio format.

    Args:
        audio_format: Audio format ('mp3', 'm4a', or 'flac')

    Returns:
        str: Directory path for the format

    Raises:
        ValueError: If audio_format is not one of the supported formats.
    """
    if audio_format == 'mp3':
        return AUDIO_OUTPUT_DIR_MP3
    if audio_format == 'm4a':
        return AUDIO_OUTPUT_DIR_M4A
    if audio_format == 'flac':
        return AUDIO_OUTPUT_DIR_FLAC
    raise ValueError(f'Unknown audio format: {audio_format}')


def organize_and_sanitize_files(video_folder: Path, audio_formats: list[str],
                                only_audio: bool, need_audio: bool) -> dict[str, dict[str, str]]:
    """
    Sanitize all downloaded file names.

    Args:
        video_folder: Path to video output directory
        audio_formats: List of audio formats (e.g., ['mp3', 'm4a', 'flac'])
        only_audio: Whether to skip video processing
        need_audio: Whether audio was downloaded

    Returns:
        dict[str, dict[str, str]]: dict with 'mp3', 'm4a', and 'flac' keys,
            each containing a mapping of final_path -> original_ytdlp_filename
    """
    original_names_mp3: dict[str, str] = {}
    original_names_m4a: dict[str, str] = {}
    original_names_flac: dict[str, str] = {}

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


def cleanup_leftover_files(video_folder: Path) -> None:
    """Remove leftover *.ytdl and *.part files from cancelled downloads.

    Args:
        video_folder: Path to the video output directory.
    """
    if not video_folder.exists():
        return
    leftover_patterns = ['*.ytdl', '*.part']
    removed_count = 0
    for pattern in leftover_patterns:
        for leftover_file in video_folder.glob(pattern):
            try:
                leftover_file.unlink()
                logger.debug(f'Removed leftover file: {leftover_file.name}')
                removed_count += 1
            except Exception as exc:
                logger.warning(f'Failed to remove {leftover_file.name}: {exc}')
    if removed_count > 0:
        logger.info(f'Cleaned up {removed_count} leftover file(s) from previous cancelled downloads')


def count_initial_files(only_audio: bool, with_audio: bool,
                        audio_formats: list[str]) -> tuple[int, int]:
    """Count existing video and audio files before download starts.

    Args:
        only_audio: Whether only audio was requested (skip video counting).
        with_audio: Whether audio extraction was requested.
        audio_formats: List of audio format strings.

    Returns:
        tuple[int, int]: (initial_video_count, initial_audio_count)
    """
    initial_video_count = 0
    initial_audio_count = 0
    if not only_audio:
        initial_video_count = count_files(
            directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv']
        )
    if with_audio or only_audio:
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            initial_audio_count += count_files(
                directory=audio_dir, extensions=[f'.{audio_format}']
            )
    return initial_video_count, initial_audio_count


def count_new_files(only_audio: bool, need_audio: bool, audio_formats: list[str],
                    initial_video_count: int, initial_audio_count: int) -> tuple[int, int]:
    """Count newly created video and audio files since download started.

    Args:
        only_audio: Whether only audio was requested (skip video counting).
        need_audio: Whether audio extraction was requested.
        audio_formats: List of audio formats to count.
        initial_video_count: File count before download started.
        initial_audio_count: File count before download started.

    Returns:
        tuple[int, int]: (new_video_count, new_audio_count)
    """
    video_count = 0
    audio_count = 0
    if not only_audio:
        final_video_count = count_files(
            directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv']
        )
        video_count = final_video_count - initial_video_count
    if need_audio:
        final_audio_count = 0
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            final_audio_count += count_files(
                directory=audio_dir, extensions=[f'.{audio_format}']
            )
        audio_count = final_audio_count - initial_audio_count
    return video_count, audio_count
