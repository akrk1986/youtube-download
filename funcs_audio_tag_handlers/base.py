"""Abstract base class for audio tag handlers."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AudioTagHandler(ABC):
    """Abstract base class for audio tag handlers."""

    # Tag name constants (overridden in subclasses)
    TAG_TITLE: str = ''
    TAG_ARTIST: str = ''
    TAG_ALBUMARTIST: str = ''
    TAG_ALBUM: str = ''

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
