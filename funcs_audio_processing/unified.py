"""
Unified audio tag processing functions that work with any audio format.
Eliminates code duplication between MP3 and M4A processing.
"""
import logging
from pathlib import Path
from typing import Any
from mutagen import MutagenError

from common_av.tag_handlers import AudioTagHandler, M4ATagHandler
from funcs_utils.artist_search import load_artists, find_artists_in_string
from project_defs import MAX_TITLE_TAG_LENGTH

logger = logging.getLogger(__name__)


def _cut_long_title(handler: AudioTagHandler, audio: Any, title: str) -> bool:
    """Cut a Title tag longer than MAX_TITLE_TAG_LENGTH; return whether the tag was changed.

    Audio and video files share this one rule, so a video and its audio carry the same title.
    """
    if len(title) <= MAX_TITLE_TAG_LENGTH:
        return False
    handler.set_tag(audio=audio, tag_name=handler.TAG_TITLE, value=title[:MAX_TITLE_TAG_LENGTH].rstrip())
    return True


def cut_title_tags_in_videos(video_folder: Path) -> None:
    """Cut long Title tags in the folder's MP4 videos, matching the cut applied to their audio.

    Args:
        video_folder: Path to the video output folder.
    """
    if not video_folder.is_dir():
        return
    handler = M4ATagHandler()  # MP4 video uses the same iTunes atoms as M4A
    for video_file in video_folder.iterdir():
        if not video_file.is_file() or video_file.suffix.lower() != '.mp4':
            continue
        try:
            video = handler.open_audio_file(file_path=video_file)
        except MutagenError as e:
            logger.warning(f"Cannot read video file '{video_file.name}' in folder '{video_folder}': {e}")
            continue
        title = handler.get_tag(audio=video, tag_name=handler.TAG_TITLE)
        if _cut_long_title(handler=handler, audio=video, title=title):
            handler.save_audio_file(audio=video, file_path=video_file)
            logger.info(f'Updated {video_file.name}: title cut to {MAX_TITLE_TAG_LENGTH} characters')


def set_artists_in_audio_files(audio_folder: Path,
                               artists_json: Path,
                               handler: AudioTagHandler,
                               original_names: dict[str, str] | None = None,
                               custom_artist: str | None = None) -> None:
    """
    Unified function to set artists in audio files (works for MP3, M4A, or any format).
    Based on artists list loaded from an external file, scan the audio file title,
    and check if it contains any artist names from the artists list.
    If found, set the tags 'artist' and 'album artist' to the artist name(s).
    A Title tag longer than MAX_TITLE_TAG_LENGTH is then cut to it -- only after detection, so
    artists credited late in a long title are still found.

    Args:
        audio_folder: Path to folder containing audio files
        artists_json: Path to artists JSON file
        handler: AudioTagHandler instance for the specific format
        original_names: Optional mapping of final_path -> original_ytdlp_filename
        custom_artist: User-specified artist (--artist). When set, artist detection is
            skipped so the custom value embedded during download is never overwritten
            (the other fixes — date format, track number, original filename — still run).
    """
    artists = load_artists(artists_json_path=artists_json)

    if original_names is None:
        original_names = {}

    for audio_file in audio_folder.glob(handler.get_file_glob()):
        try:
            audio = handler.open_audio_file(file_path=audio_file)
        except MutagenError as e:
            # Not a valid audio file or corrupted
            logger.warning(f"Cannot read audio file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error reading audio file '{audio_file.name}' in folder '{audio_folder}': {e}")
            continue

        title = handler.get_tag(audio=audio, tag_name=handler.TAG_TITLE)
        if not title:
            logger.warning(f"Skipping audio file '{audio_file.name}' in folder '{audio_folder}': No Title tag found")
            continue

        # Handle format-specific tasks (e.g., date fixing for M4A)
        upd_format_specific = handler.handle_format_specific_tasks(audio=audio)

        # Look for known artists in title — unless the user passed --artist, whose value was
        # embedded during download and must not be overwritten by detection.
        count, artist_string = 0, ''
        if custom_artist:
            logger.debug(f"Custom artist '{custom_artist}' specified, artist detection skipped")
        else:
            count, artist_string = find_artists_in_string(text=title, artists=artists)
            if count > 0:
                handler.set_tag(audio=audio, tag_name=handler.TAG_ARTIST, value=artist_string)
                # Album Artist is left untouched: this library reserves it for the dupe
                # staging workflow (see README-Dupes.md), so the pipeline no longer fills it.
            else:
                art = handler.get_tag(audio=audio, tag_name=handler.TAG_ARTIST)
                alb_art = handler.get_tag(audio=audio, tag_name=handler.TAG_ALBUMARTIST)
                logger.debug(f"No known artist in title, a/aa tags='{art}'/'{alb_art}'")

        # Cut a long title (often a whole Facebook description) once detection has read it all
        upd_title = _cut_long_title(handler=handler, audio=audio, title=title)

        # Clear track number for non-chapter files (single videos and playlists)
        upd_track = False
        if handler.has_track_number(audio=audio):
            handler.clear_track_number(audio=audio)
            upd_track = True

        if count > 0 or upd_format_specific or upd_track or upd_title:
            # Save original filename from yt-dlp (before sanitization/moving)
            original_filename = original_names.get(str(audio_file), audio_file.name)
            handler.set_original_filename(audio=audio, file_path=audio_file, original_filename=original_filename)
            # Save audio file (for M4A this saves; for MP3 this is redundant but harmless)
            handler.save_audio_file(audio=audio, file_path=audio_file)
            if count > 0:
                logger.info(f"Updated {audio_file.name}: artist set to '{artist_string}'")
            else:
                logger.info(f'Updated {audio_file.name} (metadata fixes, artist unchanged)')
        else:
            logger.debug(f'No artist found in title for {audio_file.name}')
