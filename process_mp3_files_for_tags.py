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


_windows_reserved_names = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10))
}

_invalid_windows_chars = set('<>:"/\\|?*')
_invalid_linux_chars = set('/')
_control_chars = set(chr(i) for i in range(32))  # ASCII control chars 0-31

def _is_valid_filename(filename: str) -> bool:
    if not filename:
        return False
    if filename.upper() in _windows_reserved_names:
        return False
    if any(ch in _invalid_windows_chars for ch in filename):
        return False
    if any(ch in _invalid_linux_chars for ch in filename):
        return False
    if any(ch in _control_chars for ch in filename):
        return False
    if filename[-1] in {' ', '.'}:
        return False
    return True

def _remove_emojis(text: str) -> str:
    return ''.join(c for c in text if not unicodedata.category(c).startswith('So'))

def _sanitize_filename(filename: str) -> str:
    # List of common Unicode slashes and solidus-like characters
    unicode_slashes = [
        '/',        # U+002F
        '\\',       # U+005C backslash
        '∕',        # U+2215
        '⁄',        # U+2044
        '⧸',        # U+29F8
        '⧹',        # U+29F9
        '╱',        # U+2571
        '╲',        # U+2572
        '／',       # U+FF0F
        '＼',       # U+FF3C
    ]
    # Create a regex pattern to match any of the slash-like characters, possibly surrounded by spaces
    slash_pattern = '[' + ''.join(re.escape(s) for s in unicode_slashes) + ']'
    # Replace any slash-like character (with optional surrounding spaces) with a single hyphen
    filename = re.sub(rf'\s*{slash_pattern}\s*', '-', filename)
    # Remove other invalid Windows characters and ASCII control chars
    invalid_chars = set('<>:"|?*')
    control_chars = set(chr(i) for i in range(32))
    sanitized = ''.join(
        c for c in filename
        if c not in invalid_chars and c not in control_chars
    )
    # Remove leading and trailing hyphens, spaces, and dots
    sanitized = sanitized.strip('-. ')
    # Avoid reserved Windows names
    windows_reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{i}' for i in range(1, 10)),
        *(f'LPT{i}' for i in range(1, 10))
    }
    if sanitized.upper() in windows_reserved or not sanitized:
        sanitized = f'_{sanitized}'
    return sanitized

def extract_song_info(file_name: str) -> Tuple[str, str, str]:
    pattern = r'^(.*?)\s*-\s*(\d{3})\s+(.*?)\s*\[([^\s\[\]]+)\]$'
    match = re.match(pattern, file_name)
    if not match:
        raise ValueError('String does not match the expected pattern')

    extracted_file_name = match.group(1).strip()
    song_number = match.group(2).strip()
    song_name = match.group(3).strip()
    _youtube_id = match.group(4).strip()

    extracted_file_name = _remove_emojis(extracted_file_name).strip()
    song_name = _remove_emojis(song_name).strip()

    # Sanitize file name for both Windows and Linux
    extracted_file_name = _sanitize_filename(extracted_file_name)

    return song_name, extracted_file_name, song_number
