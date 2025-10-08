"""Helper functions for main-yt-dlp.py to reduce main() complexity."""
import logging
import sys
from pathlib import Path

from funcs_process_mp3_tags import set_artists_in_mp3_files, set_tags_in_chapter_mp3_files
from funcs_process_mp4_tags import set_artists_in_m4a_files, set_tags_in_chapter_m4a_files
from funcs_utils import organize_media_files, sanitize_filenames_in_folder, validate_youtube_url
from project_defs import MAX_URL_RETRIES

logger = logging.getLogger(__name__)


def validate_and_get_url(provided_url: str | None) -> str:
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
            is_valid, error_msg = validate_youtube_url(url)

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
        is_valid, error_msg = validate_youtube_url(provided_url)
        if not is_valid:
            logger.error(f'Invalid URL: {error_msg}')
            sys.exit(1)
        return provided_url


def organize_and_sanitize_files(video_folder: Path, audio_folder: Path, audio_format: str,
                                 has_chapters: bool, only_audio: bool, need_audio: bool) -> None:
    """
    Organize chapter files and sanitize all downloaded file names.

    Args:
        video_folder: Path to video output directory
        audio_folder: Path to audio output directory
        audio_format: Audio format ('mp3', 'm4a', or 'both')
        has_chapters: Whether video has chapters
        only_audio: Whether to skip video processing
        need_audio: Whether audio was downloaded
    """
    # If chapters, move chapter files to subfolders
    if has_chapters:
        result = organize_media_files(video_dir=video_folder, audio_dir=audio_folder)

        # Check move results
        if result['mp3'] or result['m4a'] or result['mp4']:
            logger.info('Files organized successfully!')
        else:
            logger.warning('No MP3/M4A or MP4 files found in current directory.')

        if result['errors']:
            logger.error('Errors encountered:')
            for error in result['errors']:
                logger.error(f'- {error}')

    # Sanitize downloaded video file names
    if not only_audio:
        sanitize_filenames_in_folder(folder_path=video_folder)

    # Sanitize downloaded audio file names in subfolders
    if need_audio:
        if audio_format == 'mp3':
            mp3_subfolder = audio_folder / 'mp3'
            if mp3_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=mp3_subfolder)
        elif audio_format == 'm4a':
            m4a_subfolder = audio_folder / 'm4a'
            if m4a_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=m4a_subfolder)
        elif audio_format == 'both':
            mp3_subfolder = audio_folder / 'mp3'
            m4a_subfolder = audio_folder / 'm4a'
            if mp3_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=mp3_subfolder)
            if m4a_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=m4a_subfolder)


def process_audio_tags(audio_folder: Path, audio_format: str, artists_json: Path,
                       has_chapters: bool, uploader_name: str | None, video_title: str | None) -> None:
    """
    Process audio file tags based on format.

    Args:
        audio_folder: Path to audio output directory
        audio_format: Audio format ('mp3', 'm4a', or 'both')
        artists_json: Path to artists database JSON file
        has_chapters: Whether video has chapters
        uploader_name: Video uploader name (for chapter processing)
        video_title: Video title (for chapter processing)
    """
    if audio_format == 'mp3':
        mp3_subfolder = audio_folder / 'mp3'
        set_artists_in_mp3_files(mp3_folder=mp3_subfolder, artists_json=artists_json)
        if has_chapters:
            _ = set_tags_in_chapter_mp3_files(mp3_folder=mp3_subfolder, uploader=uploader_name, video_title=video_title)
    elif audio_format == 'm4a':
        m4a_subfolder = audio_folder / 'm4a'
        set_artists_in_m4a_files(m4a_folder=m4a_subfolder, artists_json=artists_json)
        if has_chapters:
            _ = set_tags_in_chapter_m4a_files(m4a_folder=m4a_subfolder, uploader=uploader_name, video_title=video_title)
    elif audio_format == 'both':
        # Process MP3 files
        logger.info('Processing MP3 files...')
        mp3_subfolder = audio_folder / 'mp3'
        set_artists_in_mp3_files(mp3_folder=mp3_subfolder, artists_json=artists_json)
        if has_chapters:
            _ = set_tags_in_chapter_mp3_files(mp3_folder=mp3_subfolder, uploader=uploader_name, video_title=video_title)

        # Process M4A files
        logger.info('Processing M4A files...')
        m4a_subfolder = audio_folder / 'm4a'
        set_artists_in_m4a_files(m4a_folder=m4a_subfolder, artists_json=artists_json)
        if has_chapters:
            _ = set_tags_in_chapter_m4a_files(m4a_folder=m4a_subfolder, uploader=uploader_name, video_title=video_title)
