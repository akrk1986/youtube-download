"""Scan FLAC files in a folder, detect artists in Title, and update tags accordingly."""
import logging
from pathlib import Path

from funcs_audio_tag_handlers import FLACTagHandler
from funcs_process_audio_tags_unified import (
    set_artists_in_audio_files,
    set_tags_in_chapter_audio_files
)

logger = logging.getLogger(__name__)


def set_artists_in_flac_files(flac_folder: Path, artists_json: Path, original_names: dict[str, str] | None = None) -> None:
    """
    Based on artists list loaded from an external file, scan the FLAC file title,
    and check if it contains any artist names from the artists list.
    If found, set the Vorbis comment tags 'artist' and 'albumartist' to the artist name(s).

    This function uses the unified audio processing with FLACTagHandler.

    Args:
        flac_folder: Path to audio files folder
        artists_json: Path to artists database JSON file
        original_names: Optional mapping of final_path -> original_ytdlp_filename
    """
    handler = FLACTagHandler()
    set_artists_in_audio_files(flac_folder, artists_json, handler, original_names)

def set_tags_in_chapter_flac_files(flac_folder: Path, uploader: str | None = None, video_title: str | None = None, original_names: dict[str, str] | None = None) -> int:
    """
    Set 'title' and 'tracknumber' tags in FLAC chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).flac
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    This function uses the unified audio processing with FLACTagHandler.

    Args:
        flac_folder: Path to audio files folder
        uploader: Video uploader name (used as artist if no artist is set)
        video_title: Video title (used as album if no album is set)
        original_names: Optional mapping of final_path -> original_ytdlp_filename

    Returns:
        Number of files whose title was modified
    """
    handler = FLACTagHandler()
    return set_tags_in_chapter_audio_files(flac_folder, handler, uploader, video_title, original_names)
