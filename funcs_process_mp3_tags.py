"""Scan MP3 files in a folder, detect artists in Title, and update tags accordingly."""
import logging
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen import MutagenError
from funcs_process_audio_tags_common import extract_chapter_info, sanitize_album_name
from funcs_artist_search import load_artists, find_artists_in_string
from funcs_utils import sanitize_string
from project_defs import GLOB_MP3_FILES

logger = logging.getLogger(__name__)

# ID3 tag name constants
TAG_TITLE = 'title'
TAG_ARTIST = 'artist'
TAG_ALBUMARTIST = 'albumartist'
TAG_ALBUM = 'album'
TAG_TRACKNUMBER = 'tracknumber'


def set_artists_in_mp3_files(mp3_folder: Path, artists_json: Path) -> None:
    """Based on artists list loaded from an external file, scan the MP3 file title,
       and check if it contains any artist names from the artists list.
       If found, set the ID3 tags 'artist' and 'album artist' to the artist name(s).
    """
    artists = load_artists(artists_json_path=artists_json)
    for mp3_file in mp3_folder.glob(GLOB_MP3_FILES):
        try:
            audio = EasyID3(mp3_file)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            audio = EasyID3()
        title = audio.get(TAG_TITLE, [''])[0]
        if not title:
            logger.warning(f"Skipping MP3 file '{mp3_file.name}' in folder '{mp3_folder}': No Title tag found")
            continue
        # Sanitize the title
        clean_title = sanitize_string(dirty_string=title)
        upd_title = clean_title != title
        # Look for known artists in title
        count, artist_string = find_artists_in_string(title, artists)
        if count > 0:
            audio[TAG_ARTIST] = [artist_string]
            audio[TAG_ALBUMARTIST] = [artist_string]
        else:
            art = audio.get(TAG_ARTIST)
            alb_art = audio.get(TAG_ALBUMARTIST)
            logger.debug(f"No known artist in title, a/aa tags='{art}'/'{alb_art}'")

        # Clear track number for non-chapter files (single videos and playlists)
        upd_track = False
        if TAG_TRACKNUMBER in audio and audio[TAG_TRACKNUMBER]:
            audio[TAG_TRACKNUMBER] = ['']  # Clear track number
            upd_track = True

        if upd_title:
            audio[TAG_TITLE] = clean_title
        if count > 0 or upd_title or upd_track:
            audio.save(mp3_file)
            logger.info(f"Updated {mp3_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            logger.debug(f'No artist found in title for {mp3_file.name}')

def set_tags_in_chapter_mp3_files(mp3_folder: Path, uploader: str = None, video_title: str = None) -> int:
    """
    Set 'title' and 'tracknumber' tags in MP3 chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).mp3
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    :param mp3_folder: Path to audio files folder
    :return: # of files whose title was modified
    """
    ctr = 0
    for mp3_file in mp3_folder.glob(GLOB_MP3_FILES):
        try:
            audio = EasyID3(mp3_file)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            audio = EasyID3()
        except MutagenError as e:
            # Not a valid MP3 file or corrupted
            logger.warning(f"Cannot read MP3 file '{mp3_file.name}' in folder '{mp3_folder}': {e}")
            continue
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error reading MP3 file '{mp3_file.name}' in folder '{mp3_folder}': {e}")
            continue

        song_name, file_name, song_number = extract_chapter_info(file_name=mp3_file.name)
        logger.debug(f"title, f_name, song_#: '{song_name}', '{file_name}, '{song_number}'")
        if song_name is None:
            continue
        try:
            audio[TAG_TITLE] = song_name
            if song_number:
                audio[TAG_TRACKNUMBER] = str(int(song_number))

            # If no artist is set and we have an uploader, use uploader as artist
            current_artist = audio.get(TAG_ARTIST, [''])
            current_albumartist = audio.get(TAG_ALBUMARTIST, [''])

            if (not current_artist or current_artist == [''] or current_artist == ['NA']) and uploader:
                audio[TAG_ARTIST] = [uploader]
                audio[TAG_ALBUMARTIST] = [uploader]
                logger.info(f"Set artist/albumartist to uploader '{uploader}' for chapter file")

            # If no album is set and we have a video title, use sanitized video title as album
            current_album = audio.get(TAG_ALBUM, [''])

            if (not current_album or current_album == [''] or current_album == ['NA']) and video_title:
                sanitized_album = sanitize_album_name(video_title)
                if sanitized_album:
                    audio[TAG_ALBUM] = [sanitized_album]
                    logger.info(f"Set album to sanitized video title '{sanitized_album}' for chapter file")

            audio.save(mp3_file)
            ctr += 1
        except Exception as e:
            # no chapter file, ignore
            logger.error(f"Failed to save MP3 tags for file '{mp3_file.name}': {e}")

    return ctr
