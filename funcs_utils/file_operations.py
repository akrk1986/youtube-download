"""File organization and management utilities."""
import logging
import shutil
from pathlib import Path
from typing import Any

from funcs_utils.string_sanitization import sanitize_string
from project_defs import GLOB_M4A_FILES, GLOB_MP3_FILES, GLOB_MP4_FILES

logger = logging.getLogger(__name__)


def organize_media_files_silent() -> dict[str, Any]:
    """
    Move MP3/M4A files to yt-audio/ and MP4 files to yt-videos/ without logging each move.
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
            if audio_file.suffix.lower() == '.mp3':
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
        dict[str, str]: dict mapping final_path -> original_ytdlp_filename (before any renames)
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
