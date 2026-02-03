"""FLAC tag handler using Vorbis Comments."""
import logging
from pathlib import Path

from mutagen.flac import FLAC

from funcs_audio_tag_handlers.base import AudioTagHandler
from project_defs import GLOB_FLAC_FILES

logger = logging.getLogger(__name__)


class FLACTagHandler(AudioTagHandler):
    """Handler for FLAC files and tags using Vorbis Comments."""

    # FLAC/Vorbis comment tag name constants
    TAG_TITLE = 'title'
    TAG_ARTIST = 'artist'
    TAG_ALBUMARTIST = 'albumartist'
    TAG_ALBUM = 'album'
    TAG_DATE = 'date'
    TAG_TRACKNUMBER = 'tracknumber'
    TAG_COMMENT = 'comment'
    TAG_ENCODEDBY = 'encodedby'

    def open_audio_file(self, file_path: Path) -> FLAC:
        """Open a FLAC file and return the FLAC object."""
        return FLAC(file_path)

    def get_tag(self, audio: FLAC, tag_name: str) -> str:
        """Get a tag value from the FLAC file."""
        value = audio.get(tag_name, [])
        return value[0] if value else ''

    def set_tag(self, audio: FLAC, tag_name: str, value: str | list[str]) -> None:
        """Set a tag value in the FLAC file."""
        if isinstance(value, str):
            audio[tag_name] = [value]
        else:
            audio[tag_name] = value

    def set_track_number(self, audio: FLAC, track_number: int) -> None:
        """Set the track number tag."""
        audio[self.TAG_TRACKNUMBER] = [str(track_number)]

    def clear_track_number(self, audio: FLAC) -> None:
        """Clear the track number tag."""
        if self.TAG_TRACKNUMBER in audio:
            del audio[self.TAG_TRACKNUMBER]

    def save_audio_file(self, audio: FLAC, file_path: Path) -> None:
        """Save the FLAC file with updated tags."""
        audio.save(file_path)

    def get_file_glob(self) -> str:
        """Get the glob pattern for FLAC files."""
        return GLOB_FLAC_FILES

    def handle_format_specific_tasks(self, audio: FLAC) -> bool:
        """
        1. Fix year format: convert YYYYMMDD to YYYY if needed.
        2. Copy PURL (video URL) to COMMENT field, but only if COMMENT is empty.
        """
        modified = False

        # Fix date format
        date_list = audio.get(self.TAG_DATE, [])
        if date_list:
            date_str = str(date_list[0])
            # If date is in YYYYMMDD format (8 digits), extract just the year (first 4 digits)
            if len(date_str) == 8 and date_str.isdigit():
                year = date_str[:4]
                audio[self.TAG_DATE] = [year]
                logger.info(f'Fixed date format: {date_str} -> {year}')
                modified = True

        # Copy PURL to COMMENT if COMMENT is empty (for consistency with MP3/M4A)
        comment_list = audio.get(self.TAG_COMMENT, [])
        if not comment_list or not comment_list[0]:
            purl_list = audio.get('purl', [])
            if purl_list and purl_list[0]:
                audio[self.TAG_COMMENT] = [purl_list[0]]
                logger.info(f'Copied PURL to COMMENT: {purl_list[0]}')
                modified = True

        return modified

    def has_track_number(self, audio: FLAC) -> bool:
        """Check if FLAC has a non-empty track number."""
        return bool(self.TAG_TRACKNUMBER in audio and audio[self.TAG_TRACKNUMBER])

    def set_original_filename(self, audio: FLAC, file_path: Path, original_filename: str | None = None) -> None:
        """
        Store the original filename in encodedby tag.

        Args:
            audio: The FLAC audio object
            file_path: Current file path
            original_filename: Original filename from yt-dlp (before sanitization/moving), defaults to file_path.name
        """
        if original_filename is None:
            original_filename = file_path.name

        # Remove file extension from original filename
        if original_filename.lower().endswith('.flac'):
            original_filename = original_filename[:-5]

        audio[self.TAG_ENCODEDBY] = [original_filename]
