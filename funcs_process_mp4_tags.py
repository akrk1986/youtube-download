"""Scan M4A files in a folder, detect artists in Title, and update tags accordingly."""
import logging
from pathlib import Path

from funcs_audio_tag_handlers import M4ATagHandler
from funcs_process_audio_tags_unified import (
    set_artists_in_audio_files,
    set_tags_in_chapter_audio_files
)

logger = logging.getLogger(__name__)

# M4A/MP4 tag name constants (using Apple's atom names) - kept for backward compatibility
TAG_TITLE = '\xa9nam'
TAG_ARTIST = '\xa9ART'
TAG_ALBUMARTIST = 'aART'
TAG_ALBUM = '\xa9alb'
TAG_DATE = '\xa9day'
TAG_TRACKNUMBER = 'trkn'


def set_artists_in_m4a_files(m4a_folder: Path, artists_json: Path) -> None:
    """
    Based on artists list loaded from an external file, scan the M4A file title,
    and check if it contains any artist names from the artists list.
    If found, set the MP4 tags 'artist' and 'album artist' to the artist name(s).

    This function now uses the unified audio processing with M4ATagHandler.
    """
    handler = M4ATagHandler()
    set_artists_in_audio_files(m4a_folder, artists_json, handler)


def set_tags_in_chapter_m4a_files(m4a_folder: Path, uploader: str | None = None, video_title: str | None = None) -> int:
    """
    Set 'title' and 'tracknumber' tags in M4A chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).m4a
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    This function now uses the unified audio processing with M4ATagHandler.

    Args:
        m4a_folder: Path to audio files folder
        uploader: Video uploader name (used as artist if no artist is set)
        video_title: Video title (used as album if no album is set)

    Returns:
        Number of files whose title was modified
    """
    handler = M4ATagHandler()
    return set_tags_in_chapter_audio_files(m4a_folder, handler, uploader, video_title)
