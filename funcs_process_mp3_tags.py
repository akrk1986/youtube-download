"""Scan MP3 files in a folder, detect artists in Title, and update tags accordingly."""
import logging
from pathlib import Path

from funcs_audio_tag_handlers import MP3TagHandler
from funcs_process_audio_tags_unified import (
    set_artists_in_audio_files,
    set_tags_in_chapter_audio_files
)

logger = logging.getLogger(__name__)

# ID3 tag name constants (kept for backward compatibility)
TAG_TITLE = 'title'
TAG_ARTIST = 'artist'
TAG_ALBUMARTIST = 'albumartist'
TAG_ALBUM = 'album'
TAG_TRACKNUMBER = 'tracknumber'


def set_artists_in_mp3_files(mp3_folder: Path, artists_json: Path, original_names: dict[str, str] | None = None) -> None:
    """
    Based on artists list loaded from an external file, scan the MP3 file title,
    and check if it contains any artist names from the artists list.
    If found, set the ID3 tags 'artist' and 'album artist' to the artist name(s).

    This function now uses the unified audio processing with MP3TagHandler.

    Args:
        mp3_folder: Path to audio files folder
        artists_json: Path to artists database JSON file
        original_names: Optional mapping of final_path -> original_ytdlp_filename
    """
    handler = MP3TagHandler()
    set_artists_in_audio_files(mp3_folder, artists_json, handler, original_names)

def set_tags_in_chapter_mp3_files(mp3_folder: Path, uploader: str | None = None, video_title: str | None = None, original_names: dict[str, str] | None = None) -> int:
    """
    Set 'title' and 'tracknumber' tags in MP3 chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).mp3
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    This function now uses the unified audio processing with MP3TagHandler.

    Args:
        mp3_folder: Path to audio files folder
        uploader: Video uploader name (used as artist if no artist is set)
        video_title: Video title (used as album if no album is set)
        original_names: Optional mapping of final_path -> original_ytdlp_filename

    Returns:
        Number of files whose title was modified
    """
    handler = MP3TagHandler()
    return set_tags_in_chapter_audio_files(mp3_folder, handler, uploader, video_title, original_names)
