"""
Audio tag handler classes for different audio formats.
Implements strategy pattern to eliminate code duplication between MP3 and M4A processing.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import logging

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError, TENC
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen import MutagenError

from project_defs import GLOB_MP3_FILES, GLOB_M4A_FILES, GLOB_FLAC_FILES

logger = logging.getLogger(__name__)


class AudioTagHandler(ABC):
    """Abstract base class for audio tag handlers."""

    @abstractmethod
    def open_audio_file(self, file_path: Path) -> Any:
        """Open an audio file and return the audio object."""
        pass

    @abstractmethod
    def get_tag(self, audio: Any, tag_name: str) -> str:
        """Get a tag value from the audio object."""
        pass

    @abstractmethod
    def set_tag(self, audio: Any, tag_name: str, value: str | list[str]) -> None:
        """Set a tag value in the audio object."""
        pass

    @abstractmethod
    def set_track_number(self, audio: Any, track_number: int) -> None:
        """Set the track number tag."""
        pass

    @abstractmethod
    def clear_track_number(self, audio: Any) -> None:
        """Clear the track number tag."""
        pass

    @abstractmethod
    def save_audio_file(self, audio: Any, file_path: Path) -> None:
        """Save the audio file with updated tags."""
        pass

    @abstractmethod
    def get_file_glob(self) -> str:
        """Get the glob pattern for files of this format."""
        pass

    @abstractmethod
    def handle_format_specific_tasks(self, audio: Any) -> bool:
        """
        Handle any format-specific tasks (e.g., date fixing for M4A).
        Returns True if any modifications were made.
        """
        pass

    @abstractmethod
    def has_track_number(self, audio: Any) -> bool:
        """Check if audio has a non-empty track number."""
        pass

    @abstractmethod
    def set_original_filename(self, audio: Any, file_path: Path, original_filename: str | None = None) -> None:
        """
        Store the original filename in format-specific tag.

        Args:
            audio: The audio object
            file_path: Current file path
            original_filename: Original filename from yt-dlp (before sanitization/moving), defaults to file_path.name
        """
        pass


class MP3TagHandler(AudioTagHandler):
    """Handler for MP3 files using EasyID3."""

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
        """Save the MP3 file with updated tags."""
        audio.save(file_path)

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

        # Save EasyID3 first to ensure tags are written
        audio.save(file_path)
        # Then use ID3 (not EasyID3) to access TENC frame
        id3 = ID3(file_path)
        # TENC frame: encoding, text (the original filename from yt-dlp without extension)
        id3.add(TENC(encoding=3, text=original_filename))
        id3.save(file_path)
        # Reload the audio object to reflect the changes
        audio.load(file_path)


class M4ATagHandler(AudioTagHandler):
    """Handler for M4A files using MP4."""

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


class FLACTagHandler(AudioTagHandler):
    """Handler for FLAC files using Vorbis Comments."""

    # FLAC/Vorbis comment tag name constants
    TAG_TITLE = 'title'
    TAG_ARTIST = 'artist'
    TAG_ALBUMARTIST = 'albumartist'
    TAG_ALBUM = 'album'
    TAG_DATE = 'date'
    TAG_TRACKNUMBER = 'tracknumber'
    TAG_GENRE = 'genre'
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
        Fix year format: convert YYYYMMDD to YYYY if needed.
        Copy PURL (video URL) to COMMENT field if COMMENT is empty.
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
