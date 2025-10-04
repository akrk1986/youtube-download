"""Scan MP3/M4A chapter files in a folder, detect details in the file name."""
import re
import unicodedata
from typing import Tuple

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

def extract_chapter_info(file_name: str) -> Tuple[str | None, str | None, str | None]:
    """Given a file name which is an MP3/MP4 chapter, extract relevant parts:
    - file name
    - song number
    - song name.
    """
    pattern = r'^(.*?)\s*-\s*(\d{3})\s+(.*?)\s*\[([^\s\[\]]+)\]\.(?:mp3|m4a|MP3|M4A)$'
    match = re.match(pattern, file_name)
    if not match:
        print(f"File name '{file_name}' does not match the chapter pattern, skipped")
        return None, None, None

    extracted_file_name = match.group(1).strip()
    song_number = match.group(2).strip()
    song_name = match.group(3).strip()
    _youtube_id = match.group(4).strip()

    extracted_file_name = _remove_emojis(extracted_file_name).strip()
    song_name = _remove_emojis(song_name).strip()

    # Sanitize file name for both Windows and Linux
    extracted_file_name = _sanitize_filename(extracted_file_name)

    return song_name, extracted_file_name, song_number

def sanitize_album_name(title: str) -> str:
    """Sanitize video title to use as album name.

    Args:
        title: The video title to sanitize

    Returns:
        Sanitized title limited to 64 characters, with emojis and special characters removed
    """
    if not title:
        return ''

    # Remove emojis first
    no_emojis = _remove_emojis(title)

    # Apply filename sanitization (removes special chars, etc.)
    sanitized = _sanitize_filename(no_emojis)

    # Limit to 64 characters
    if len(sanitized) > 64:
        sanitized = sanitized[:64].rstrip()

    return sanitized
