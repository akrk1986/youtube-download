"""File organization and management utilities."""
import logging
import shutil
from pathlib import Path
from typing import Any

from funcs_utils.string_sanitization import sanitize_string
from project_defs import (AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_FLAC,
                          AUDIO_OUTPUT_DIR_M4A, GLOB_FLAC_FILES,
                          GLOB_FLAC_FILES_UPPER, GLOB_M4A_FILES,
                          GLOB_M4A_FILES_UPPER, GLOB_MP3_FILES,
                          GLOB_MP3_FILES_UPPER, GLOB_MP4_FILES)

logger = logging.getLogger(__name__)


def organize_media_files(video_dir: Path) -> dict:
    """
    Move all MP3/M4A/FLAC files to their respective directories and all MP4 files to video directory.
    - MP3 files -> yt-audio/
    - M4A files -> yt-audio-m4a/
    - FLAC files -> yt-audio-flac/
    - MP4 files -> yt-videos/
    Creates the directories if they don't exist.

    Returns:
        dict: Summary with moved files counts, any errors, and original_names mapping.
              original_names maps final_path -> original_filename_before_move
    """
    current_dir = Path.cwd()

    moved_files: dict[str, Any] = {'mp3': [], 'mp4': [], 'm4a': [], 'flac': [], 'errors': [], 'original_names': {}}

    # Get all audio-like files including case variations
    audio_files = (list(current_dir.glob(GLOB_MP3_FILES)) +
                   list(current_dir.glob(GLOB_M4A_FILES)) +
                   list(current_dir.glob(GLOB_FLAC_FILES)) +
                   list(current_dir.glob(GLOB_MP3_FILES_UPPER)) +
                   list(current_dir.glob(GLOB_M4A_FILES_UPPER)) +
                   list(current_dir.glob(GLOB_FLAC_FILES_UPPER)))

    # Find and move MP3/M4A/FLAC files to their respective directories
    for audio_file in audio_files:
        try:
            if audio_file.suffix.lower() == '.mp3':
                dest_dir = Path(AUDIO_OUTPUT_DIR)
                moved_files['mp3'].append(audio_file.name)
                dest_dir_name = AUDIO_OUTPUT_DIR
            elif audio_file.suffix.lower() == '.m4a':
                dest_dir = Path(AUDIO_OUTPUT_DIR_M4A)
                moved_files['m4a'].append(audio_file.name)
                dest_dir_name = AUDIO_OUTPUT_DIR_M4A
            elif audio_file.suffix.lower() == '.flac':
                dest_dir = Path(AUDIO_OUTPUT_DIR_FLAC)
                moved_files['flac'].append(audio_file.name)
                dest_dir_name = AUDIO_OUTPUT_DIR_FLAC
            else:
                # Skip files that are not MP3, M4A, or FLAC
                logger.warning(
                    f"Skipping unsupported audio file '{audio_file.name}' with extension '{audio_file.suffix}'")
                continue

            # Create destination directory if it doesn't exist
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Store original filename before moving
            original_name = audio_file.name
            destination = dest_dir / audio_file.name
            shutil.move(str(audio_file), str(destination))
            # Map destination path to original name
            moved_files['original_names'][str(destination)] = original_name
            logger.info(f'Moved {audio_file.name} -> {dest_dir_name}/')
        except Exception as e:
            error_msg = f'Error moving {audio_file.name}: {str(e)}'
            moved_files['errors'].append(error_msg)
            logger.error(error_msg)

    # Find and move MP4 files
    for mp4_file in current_dir.glob(GLOB_MP4_FILES):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
            logger.info(f'Moved {mp4_file.name} -> yt-videos/')
        except Exception as e:
            error_msg = f'Error moving {mp4_file.name}: {str(e)}'
            moved_files['errors'].append(error_msg)
            logger.error(error_msg)

    # Print summary
    logger.info('Summary:')
    logger.info(f'MP3 files moved: {len(moved_files["mp3"])}')
    logger.info(f'M4A files moved: {len(moved_files["m4a"])}')
    logger.info(f'FLAC files moved: {len(moved_files["flac"])}')
    logger.info(f'MP4 files moved: {len(moved_files["mp4"])}')
    if moved_files['errors']:
        logger.warning(f'Errors: {len(moved_files["errors"])}')
    return moved_files


def organize_media_files_silent() -> dict:
    """
    Same as organize_media_files() but without print statements.
    Returns only the summary dictionary.
    """
    current_dir = Path('.')
    audio_dir = current_dir / 'yt-audio'
    video_dir = current_dir / 'yt-videos'

    # Create directories if they don't exist
    audio_dir.mkdir(exist_ok=True)
    video_dir.mkdir(exist_ok=True)

    moved_files: dict[str, Any] = {'mp3': [], 'mp4': [], 'm4a': [], 'errors': []}

    audio_files = list(current_dir.glob(GLOB_MP3_FILES)) + list(current_dir.glob(GLOB_M4A_FILES))

    # Move MP3 files
    for audio_file in audio_files:
        try:
            destination = audio_dir / audio_file.name
            shutil.move(str(audio_file), str(destination))
            if audio_file.suffix == 'mp3':
                moved_files['mp3'].append(audio_file.name)
            else:
                moved_files['m4a'].append(audio_file.name)
        except Exception as e:
            moved_files['errors'].append(f'Error moving {audio_file.name}: {str(e)}')

    # Move MP4 files
    for mp4_file in current_dir.glob(GLOB_MP4_FILES):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
        except Exception as e:
            moved_files['errors'].append(f'Error moving {mp4_file.name}: {str(e)}')

    return moved_files


def sanitize_filenames_in_folder(folder_path: Path,
                                 original_names: dict[str, str] | None = None) -> dict[str, str]:
    """
    Sanitize file names in the folder by removing leading unwanted characters.

    Args:
        folder_path: Path to folder containing files to sanitize
        original_names: Optional mapping of current_path -> original_filename to preserve through renames

    Returns:
        dict mapping final_path -> original_ytdlp_filename (before any renames)
    """
    ctr = 0
    result_mapping = {}

    # Start with incoming mapping if provided
    if original_names:
        result_mapping.update(original_names)

    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = sanitize_string(dirty_string=file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    # Get the original filename for this file
                    old_path_str = str(file_path)
                    original_filename = result_mapping.get(old_path_str, file_path.name)

                    # Rename the file
                    file_path.rename(new_path)

                    # Update mapping: remove old path, add new path
                    if old_path_str in result_mapping:
                        del result_mapping[old_path_str]
                    result_mapping[str(new_path)] = original_filename

                    ctr += 1
                    logger.info(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    logger.warning(f"Skipped (target exists): '{new_name}'")
                    # Keep the existing mapping for this file
                    old_path_str = str(file_path)
                    if old_path_str in result_mapping:
                        result_mapping[old_path_str] = result_mapping[old_path_str]
            else:
                # No rename needed, but preserve mapping if it exists
                file_path_str = str(file_path)
                if file_path_str not in result_mapping:
                    result_mapping[file_path_str] = file_path.name

    logger.info(f"Renamed {ctr} files in folder '{folder_path}'")
    return result_mapping
