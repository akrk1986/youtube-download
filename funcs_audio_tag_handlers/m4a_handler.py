"""M4A tag handler using MP4."""
import logging
from pathlib import Path

from mutagen.mp4 import MP4

from funcs_audio_tag_handlers.base import AudioTagHandler
from project_defs import GLOB_M4A_FILES

logger = logging.getLogger(__name__)


class M4ATagHandler(AudioTagHandler):
    """Handler for M4A files and tags using MP4."""

    # M4A/MP4 tag name constants (using Apple's atom names)
    TAG_TITLE = '\xa9nam'
    TAG_ARTIST = '\xa9ART'
    TAG_ALBUMARTIST = 'aART'
    TAG_ALBUM = '\xa9alb'
    TAG_DATE = '\xa9day'
    TAG_TRACKNUMBER = 'trkn'
    TAG_LYRICS = '\xa9lyr'

    def open_audio_file(self, file_path: Path) -> MP4:
        """Open an M4A file and return the MP4 object."""
        return MP4(file_path)

    def get_tag(self, audio: MP4, tag_name: str) -> str:
        """Get a tag value from the M4A file."""
        value = audio.get(tag_name, [])
        return value[0] if value else ''

    def set_tag(self, audio: MP4, tag_name: str, value: str | list[str]) -> None:
        """Set a tag value in the M4A file."""
        if isinstance(value, str):
            audio[tag_name] = [value]
        else:
            audio[tag_name] = value

    def set_track_number(self, audio: MP4, track_number: int) -> None:
        """Set the track number tag."""
        audio[self.TAG_TRACKNUMBER] = [(track_number, 0)]

    def clear_track_number(self, audio: MP4) -> None:
        """Clear the track number tag."""
        audio[self.TAG_TRACKNUMBER] = []

    def save_audio_file(self, audio: MP4, file_path: Path) -> None:
        """Save the M4A file with updated tags."""
        audio.save(file_path)

    def get_file_glob(self) -> str:
        """Get the glob pattern for M4A files."""
        return GLOB_M4A_FILES

    def handle_format_specific_tasks(self, audio: MP4) -> bool:
        """Fix year format: convert YYYYMMDD to YYYY if needed."""
        date_list = audio.get(self.TAG_DATE, [])
        if date_list:
            date_str = str(date_list[0])
            # If date is in YYYYMMDD format (8 digits), extract just the year (first 4 digits)
            if len(date_str) == 8 and date_str.isdigit():
                year = date_str[:4]
                audio[self.TAG_DATE] = [year]
                logger.info(f'Fixed date format: {date_str} -> {year}')
                return True
        return False

    def has_track_number(self, audio: MP4) -> bool:
        """Check if M4A has a non-empty track number."""
        return bool(self.TAG_TRACKNUMBER in audio and audio[self.TAG_TRACKNUMBER])

    def set_original_filename(self, audio: MP4, file_path: Path, original_filename: str | None = None) -> None:
        """
        Store the original filename in ©lyr tag (lyrics).

        Args:
            audio: The MP4 audio object
            file_path: Current file path
            original_filename: Original filename from yt-dlp (before sanitization/moving), defaults to file_path.name
        """
        if original_filename is None:
            original_filename = file_path.name

        # Remove file extension from original filename
        if original_filename.lower().endswith('.m4a'):
            original_filename = original_filename[:-4]

        audio[self.TAG_LYRICS] = [original_filename]
