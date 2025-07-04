"""Scan MP3 files in a folder, detect artists in Title, and update tags accordingly."""
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
import re
import unicodedata
from typing import Tuple
from artist_search import load_artists, find_artists_in_string
from utils import sanitize_string


def set_artists_in_mp3_files(mp3_folder: Path, artists_json: Path) -> None:
    """Based on artists list loaded from an external file, scan the MP3 file title,
     and check if it contains any artist names from the artists list.
    If found, set the ID3 tags 'artist' and 'album artist' to the artist name(s).
    """
    artists = load_artists(artists_json_path=artists_json)
    for mp3_file in mp3_folder.glob("*.mp3"):
        try:
            audio = EasyID3(mp3_file)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            audio = EasyID3()
        title = audio.get("title", [""])[0]
        if not title:
            print(f"Skipping {mp3_file.name}: No Title tag found.")
            continue
        # Sanitize the title
        clean_title = sanitize_string(dirty_string=title)
        upd_title = clean_title != title
        # Look for known artists in title
        count, artist_string = find_artists_in_string(title, artists)
        if count > 0:
            audio["artist"] = [artist_string]
            audio["albumartist"] = [artist_string]
        if upd_title:
            audio['title'] = clean_title
        if count > 0 or upd_title:
            audio.save(mp3_file)
            print(f"Updated {mp3_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            print(f"No artist found in title for {mp3_file.name}")

def set_title_in_chapter_mp3_files(mp3_folder: Path) -> int:
    """
    Clean up 'title' tag in MP3 chapter files.
    File name pattern:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - (\\d\\d\\d) (.*) (\\[.*\\])
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    :param mp3_folder: Path to audio files folder
    :return: # of files whose title was modified
    """
    for mp3_file in mp3_folder.glob("*.mp3"):
        song_name, file_name, song_number = extract_song_info(file_name=mp3_file.name)
        print(f"song_name, f_name, song_#: '{song_name}', '{file_name}, '{song_number}'")
    return 0

def _remove_emojis(text: str) -> str:
    # Remove all emoji characters (Symbols, Other)
    return ''.join(c for c in text if not unicodedata.category(c).startswith('So'))

def extract_song_info(file_name: str) -> Tuple[str, str, str]:
    """Return sanitized parts of the string by the pattern."""
    # Regex pattern:
    # Group 1: file name (anything, lazy)
    # Group 2: song number (3 digits)
    # Group 3: song name (anything, lazy)
    # Group 4: YouTube ID (no whitespace, no emojis)
    pattern = r'^(.*?)\s*-\s*(\d{3})\s+(.*?)\s*\[([^\s\[\]]+)\]$'
    match = re.match(pattern, file_name)
    if not match:
        raise ValueError('String does not match the expected pattern')

    file_name = match.group(1).strip()
    song_number = match.group(2).strip()
    song_name = match.group(3).strip()
    _youtube_id = match.group(4).strip()  # no emojis or whitespace expected here

    # Remove emojis from file_name and song_name only
    file_name = _remove_emojis(file_name).strip()
    song_name = _remove_emojis(song_name).strip()

    return song_name, file_name, song_number
