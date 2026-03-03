"""Audio tag processing utilities."""
import logging
from pathlib import Path

from funcs_for_main_yt_dlp.file_organization import (
    get_audio_dir_for_format,
)
from funcs_audio_processing import (
    set_artists_for_format,
    set_chapter_tags_for_format,
)

logger = logging.getLogger(__name__)


def process_audio_tags(
        audio_formats: list[str],
        artists_json: Path,
        has_chapters: bool,
        uploader_name: str | None,
        video_title: str | None,
        original_names: dict[str, dict[str, str]] | None = None
) -> None:
    """
    Process audio file tags based on formats.

    Args:
        audio_formats: List of audio formats
            (e.g., ['mp3', 'm4a', 'flac'])
        artists_json: Path to artists database JSON file
        has_chapters: Whether video has chapters
        uploader_name: Video uploader name
        video_title: Video title (for chapter processing)
        original_names: Optional dict with format keys
            containing final_path -> original_ytdlp_filename
    """
    if original_names is None:
        original_names = {'mp3': {}, 'm4a': {}, 'flac': {}}

    for audio_format in audio_formats:
        if len(audio_formats) > 1:
            logger.info(
                f'Processing {audio_format.upper()} files...'
            )

        audio_dir = Path(
            get_audio_dir_for_format(
                audio_format=audio_format
            )
        )
        format_names = original_names.get(audio_format, {})

        set_artists_for_format(
            audio_format, audio_folder=audio_dir,
            artists_json=artists_json,
            original_names=format_names
        )
        if has_chapters:
            set_chapter_tags_for_format(
                audio_format, audio_folder=audio_dir,
                uploader=uploader_name,
                video_title=video_title,
                original_names=format_names
            )
