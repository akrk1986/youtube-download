"""
Unified audio tag processing functions that work with any audio format.
Eliminates code duplication between MP3 and M4A processing.
"""
import logging
from pathlib import Path
from mutagen import MutagenError

from funcs_audio_tag_handlers import AudioTagHandler
from funcs_process_audio_tags_common import extract_chapter_info, sanitize_album_name
from funcs_artist_search import load_artists, find_artists_in_string
from funcs_utils import sanitize_string

logger = logging.getLogger(__name__)


def set_artists_in_audio_files(audio_folder: Path, artists_json: Path, handler: AudioTagHandler) -> None:
    """
    Unified function to set artists in audio files (works for MP3, M4A, or any format).
    Based on artists list loaded from an external file, scan the audio file title,
    and check if it contains any artist names from the artists list.
    If found, set the tags 'artist' and 'album artist' to the artist name(s).

    Args:
        audio_folder: Path to folder containing audio files
        artists_json: Path to artists JSON file
        handler: AudioTagHandler instance for the specific format
    """
    artists = load_artists(artists_json_path=artists_json)

    for audio_file in audio_folder.glob(handler.get_file_glob()):
        try:
            audio = handler.open_audio_file(audio_file)
        except MutagenError as e:
            # Not a valid audio file or corrupted
            logger.warning(f"Cannot read audio file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error reading audio file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue

        title = handler.get_tag(audio, handler.TAG_TITLE)
        if not title:
            logger.warning(f"Skipping audio file '{audio_file.name}' in folder '{audio_folder}': No Title tag found")
            continue

        # Sanitize the title
        clean_title = sanitize_string(dirty_string=title)
        upd_title = clean_title != title

        # Handle format-specific tasks (e.g., date fixing for M4A)
        upd_format_specific = handler.handle_format_specific_tasks(audio)

        # Look for known artists in title
        count, artist_string = find_artists_in_string(title, artists)
        if count > 0:
            handler.set_tag(audio, handler.TAG_ARTIST, artist_string)
            handler.set_tag(audio, handler.TAG_ALBUMARTIST, artist_string)
        else:
            art = handler.get_tag(audio, handler.TAG_ARTIST)
            alb_art = handler.get_tag(audio, handler.TAG_ALBUMARTIST)
            logger.debug(f"No known artist in title, a/aa tags='{art}'/'{alb_art}'")

        # Clear track number for non-chapter files (single videos and playlists)
        upd_track = False
        if handler.has_track_number(audio):
            handler.clear_track_number(audio)
            upd_track = True

        if upd_title:
            handler.set_tag(audio, handler.TAG_TITLE, clean_title)

        if count > 0 or upd_title or upd_format_specific or upd_track:
            # Save original filename (MP3 saves internally, M4A just sets tag)
            handler.set_original_filename(audio, audio_file)
            # Save audio file (for M4A this saves; for MP3 this is redundant but harmless)
            handler.save_audio_file(audio, audio_file)
            logger.info(f"Updated {audio_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            logger.debug(f'No artist found in title for {audio_file.name}')


def set_tags_in_chapter_audio_files(
    audio_folder: Path,
    handler: AudioTagHandler,
    uploader: str | None = None,
    video_title: str | None = None
) -> int:
    """
    Unified function to set tags in chapter audio files (works for MP3, M4A, or any format).
    Set 'title' and 'tracknumber' tags in chapter files in the given folder.

    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID>]

    Args:
        audio_folder: Path to audio files folder
        handler: AudioTagHandler instance for the specific format
        uploader: Video uploader name (used as artist if no artist is set)
        video_title: Video title (used as album if no album is set)

    Returns:
        Number of files whose title was modified
    """
    ctr = 0

    for audio_file in audio_folder.glob(handler.get_file_glob()):
        try:
            audio = handler.open_audio_file(audio_file)
        except MutagenError as e:
            # Not a valid audio file or corrupted
            logger.warning(f"Cannot read audio chapter file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error reading audio chapter file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue

        song_name, file_name, song_number = extract_chapter_info(file_name=audio_file.name)
        logger.debug(f"title, f_name, song_#: '{song_name}', '{file_name}', '{song_number}'")
        if song_name is None:
            continue

        try:
            handler.set_tag(audio, handler.TAG_TITLE, song_name)
            if song_number:
                handler.set_track_number(audio, int(song_number))

            # Handle format-specific tasks (e.g., date fixing for M4A)
            handler.handle_format_specific_tasks(audio)

            # If no artist is set and we have an uploader, use uploader as artist
            current_artist = handler.get_tag(audio, handler.TAG_ARTIST)
            current_albumartist = handler.get_tag(audio, handler.TAG_ALBUMARTIST)

            if (not current_artist or current_artist == '' or current_artist == 'NA') and uploader:
                handler.set_tag(audio, handler.TAG_ARTIST, uploader)
                handler.set_tag(audio, handler.TAG_ALBUMARTIST, uploader)
                logger.info(f"Set artist/albumartist to uploader '{uploader}' for chapter file")

            # If no album is set and we have a video title, use sanitized video title as album
            current_album = handler.get_tag(audio, handler.TAG_ALBUM)

            if (not current_album or current_album == '' or current_album == 'NA') and video_title:
                sanitized_album = sanitize_album_name(video_title)
                if sanitized_album:
                    handler.set_tag(audio, handler.TAG_ALBUM, sanitized_album)
                    logger.info(f"Set album to sanitized video title '{sanitized_album}' for chapter file")

            # Save original filename (MP3 saves internally, M4A just sets tag)
            handler.set_original_filename(audio, audio_file)
            # Save audio file (for M4A this saves; for MP3 this is redundant but harmless)
            handler.save_audio_file(audio, audio_file)
            ctr += 1
        except Exception as e:
            # no chapter file, ignore
            logger.error(f"Failed to save audio tags for file '{audio_file.name}': {e}")

    return ctr
