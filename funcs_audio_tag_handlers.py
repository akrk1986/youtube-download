"""
Audio tag handler classes for different audio formats.
Implements strategy pattern to eliminate code duplication between MP3 and M4A processing.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import logging

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp4 import MP4
from mutagen import MutagenError

from project_defs import GLOB_MP3_FILES, GLOB_M4A_FILES

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


class M4ATagHandler(AudioTagHandler):
    """Handler for M4A files using MP4."""

    # M4A/MP4 tag name constants (using Apple's atom names)
    TAG_TITLE = '\xa9nam'
    TAG_ARTIST = '\xa9ART'
    TAG_ALBUMARTIST = 'aART'
    TAG_ALBUM = '\xa9alb'
    TAG_DATE = '\xa9day'
    TAG_TRACKNUMBER = 'trkn'

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
