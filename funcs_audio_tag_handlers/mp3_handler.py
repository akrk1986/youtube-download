"""MP3 tag handler using EasyID3."""
import logging
from pathlib import Path

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError, TENC

from funcs_audio_tag_handlers.base import AudioTagHandler
from project_defs import GLOB_MP3_FILES

logger = logging.getLogger(__name__)


def _force_utf16_encoding(file_path: Path) -> None:
    """
    Force UTF-16 encoding (encoding=1) for all text frames in an MP3 file.
    This ensures maximum compatibility with mobile devices and players that have
    poor UTF-8 support, especially for non-Latin scripts (Turkish, Greek, Hebrew, etc.).

    Args:
        file_path: Path to the MP3 file to fix
    """
    try:
        id3 = ID3(file_path)

        # List of text frame types that need UTF-16 encoding
        # These are the frames that EasyID3 creates
        text_frame_ids = ['TIT2', 'TPE1', 'TPE2', 'TALB', 'TDRC', 'TRCK', 'TENC', 'COMM']

        modified = False
        for frame_id in text_frame_ids:
            if frame_id in id3:
                frame = id3[frame_id]
                # Check if frame has text attribute and is not already UTF-16
                if hasattr(frame, 'encoding') and frame.encoding != 1:
                    frame.encoding = 1  # Force UTF-16 with BOM
                    modified = True
                    logger.debug(f'Forced UTF-16 encoding for {frame_id} frame')

        if modified:
            id3.save(file_path, v2_version=3)
            logger.debug(f'Saved MP3 with UTF-16 encoding: {file_path.name}')
    except Exception as e:
        logger.warning(f'Failed to force UTF-16 encoding for {file_path.name}: {e}')


class MP3TagHandler(AudioTagHandler):
    """Handler for MP3 files and tags using EasyID3."""

    # ID3 tag name constants
    TAG_TITLE = 'title'
    TAG_ARTIST = 'artist'
    TAG_ALBUMARTIST = 'albumartist'
    TAG_ALBUM = 'album'
    TAG_TRACKNUMBER = 'tracknumber'

    def open_audio_file(self, file_path: Path) -> EasyID3:
        """Open an MP3 file and return the EasyID3 object."""
        try:
            return EasyID3(file_path)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            return EasyID3()

    def get_tag(self, audio: EasyID3, tag_name: str) -> str:
        """Get a tag value from the MP3 file."""
        value = audio.get(tag_name, [''])
        return value[0] if value else ''

    def set_tag(self, audio: EasyID3, tag_name: str, value: str | list[str]) -> None:
        """Set a tag value in the MP3 file."""
        if isinstance(value, str):
            audio[tag_name] = [value]
        else:
            audio[tag_name] = value

    def set_track_number(self, audio: EasyID3, track_number: int) -> None:
        """Set the track number tag."""
        audio[self.TAG_TRACKNUMBER] = str(track_number)

    def clear_track_number(self, audio: EasyID3) -> None:
        """Clear the track number tag."""
        audio[self.TAG_TRACKNUMBER] = ['']

    def save_audio_file(self, audio: EasyID3, file_path: Path) -> None:
        """Save the MP3 file with updated tags using ID3v2.3 and UTF-16 encoding for maximum mobile compatibility."""
        audio.save(file_path, v2_version=3)
        # Force UTF-16 encoding for all text frames to ensure Turkish/Greek/Hebrew display correctly on all devices
        _force_utf16_encoding(file_path=file_path)

    def get_file_glob(self) -> str:
        """Get the glob pattern for MP3 files."""
        return GLOB_MP3_FILES

    def handle_format_specific_tasks(self, audio: EasyID3) -> bool:
        """MP3 files don't need format-specific tasks."""
        return False

    def has_track_number(self, audio: EasyID3) -> bool:
        """Check if MP3 has a non-empty track number."""
        return bool(self.TAG_TRACKNUMBER in audio and audio[self.TAG_TRACKNUMBER])

    def set_original_filename(self, audio: EasyID3, file_path: Path, original_filename: str | None = None) -> None:
        """
        Store the original filename in TENC (Encoded by) tag.
        Note: This method saves the file because TENC requires direct ID3 access.

        Args:
            audio: The EasyID3 audio object
            file_path: Current file path
            original_filename: Original filename from yt-dlp (before sanitization/moving), defaults to file_path.name
        """
        if original_filename is None:
            original_filename = file_path.name

        # Remove file extension from original filename
        if original_filename.lower().endswith('.mp3'):
            original_filename = original_filename[:-4]

        # Save EasyID3 first to ensure tags are written (using ID3v2.3 for compatibility)
        audio.save(file_path, v2_version=3)
        # Then use ID3 (not EasyID3) to access TENC frame
        id3 = ID3(file_path)
        # TENC frame: encoding=1 is UTF-16 with BOM for better mobile device compatibility
        id3.add(TENC(encoding=1, text=original_filename))
        id3.save(file_path, v2_version=3)
        # Force UTF-16 encoding for all text frames to ensure Turkish/Greek/Hebrew display correctly on all devices
        _force_utf16_encoding(file_path=file_path)
        # Reload the audio object to reflect the changes
        audio.load(file_path)
