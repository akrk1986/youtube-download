"""Audio tag processing utilities."""
import logging
from pathlib import Path

from funcs_for_main_yt_dlp.file_organization import get_audio_dir_for_format
from funcs_audio_processing import (
    set_artists_in_flac_files,
    set_tags_in_chapter_flac_files,
    set_artists_in_m4a_files,
    set_tags_in_chapter_m4a_files,
    set_artists_in_mp3_files,
    set_tags_in_chapter_mp3_files
)

logger = logging.getLogger(__name__)


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

        audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))

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
