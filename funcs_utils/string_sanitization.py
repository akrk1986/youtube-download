"""String and filename sanitization utilities."""
import re
import unicodedata

import emoji

from project_defs import LEADING_NONALNUM_PATTERN, MULTIPLE_SPACES_PATTERN

# Regex: remove leading non-alphanumeric characters (English+Greek+Hebrew+French+Turkish), including spaces
pattern = re.compile(LEADING_NONALNUM_PATTERN)


def sanitize_string(dirty_string: str) -> str:
    """
    Sanitize filename by:
    1. Replacing emojis with spaces
    2. Replacing foreign characters (not English/French/Greek/Hebrew/Turkish) with spaces
    3. Removing leading unwanted characters and spaces
    4. Compressing multiple spaces into one
    5. Removing trailing spaces before file extension
    """
    if not dirty_string:
        return dirty_string

    # Supported file extensions (case-insensitive)
    valid_extensions = {'mp4', 'wmv', 'mkv', 'mp3', 'm4a', 'flac', 'webm', 'avi', 'mov', 'txt'}

    # Split filename and extension using the last '.'
    # Only treat as extension if it's a supported format
    if '.' in dirty_string:
        name_part, extension = dirty_string.rsplit('.', 1)
        if extension.lower() in valid_extensions:
            has_extension = True
        else:
            # Not a valid extension, treat as part of basename
            name_part = dirty_string
            extension = ''
            has_extension = False
    else:
        name_part = dirty_string
        extension = ''
        has_extension = False

    # 1. Replace all emojis with spaces
    name_part = emoji.replace_emoji(name_part, replace=' ')

    # 2. Replace foreign characters with spaces
    # noinspection SpellCheckingInspection
    # Keep: English (a-z, A-Z), French (àáâãäåæçèéêëìíîïðñòóôõöøùúûüýÿ),
    #       Turkish (çğıöşüÇĞİÖŞÜ), Greek (α-ω, Α-Ω), Hebrew (א-ת),
    #       numbers (0-9), and common punctuation
    allowed_chars = []
    for char in name_part:
        # English letters and numbers
        if char.isascii() and (char.isalnum() or char in ' .,;!()-_[]{}'):
            allowed_chars.append(char)
        # Greek letters (main range)
        elif '\u0370' <= char <= '\u03FF':
            allowed_chars.append(char)
        # Hebrew letters
        elif '\u05d0' <= char <= '\u05ea':
            allowed_chars.append(char)
        # French and Turkish characters (Latin-1 Supplement)
        # Includes: French accented letters and Turkish Ö, Ü, Ç (both cases)
        elif '\u00c0' <= char <= '\u00ff':
            allowed_chars.append(char)
        # Additional French and Turkish characters in Latin Extended-A
        # Includes: French ligatures, Turkish İ, ı, Ğ, ğ, Ş, ş
        elif char in ('ĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁł'
                      'ŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž'):
            allowed_chars.append(char)
        else:
            # Replace foreign character with space
            allowed_chars.append(' ')

    name_part = ''.join(allowed_chars)

    # 3. Remove leading unwanted characters (using existing pattern)
    name_part = pattern.sub('', name_part)

    # 4. Compress multiple spaces into one
    name_part = re.sub(MULTIPLE_SPACES_PATTERN, ' ', name_part)

    # 5. Remove leading and trailing spaces
    name_part = name_part.strip()

    # 6. Truncate to ensure total filename length <= 64 characters
    max_filename_length = 64
    if has_extension:
        # Account for dot and extension length
        max_name_length = max_filename_length - 1 - len(extension)
        if len(name_part) > max_name_length:
            name_part = name_part[:max_name_length].rstrip()
    else:
        if len(name_part) > max_filename_length:
            name_part = name_part[:max_filename_length].rstrip()

    # Reconstruct filename
    if has_extension and name_part:
        return f'{name_part}.{extension}'
    elif has_extension:
        # If name_part is empty, but we had an extension, keep the extension
        return f'untitled.{extension}'
    return name_part


def remove_diacritics(text: str) -> str:
    """
    Remove diacritics from Greek text by normalizing to NFD form
    and filtering out combining characters (diacritical marks).
    """
    # Normalize to NFD (decomposed form)
    normalized = unicodedata.normalize('NFD', text)
    # Filter out combining characters (diacritics)
    without_diacritics = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'
    )
    return without_diacritics


def greek_search(big_string: str, sub_string: str) -> bool:
    """
    Check if sub_string appears in big_string (case-insensitive), ignoring Greek diacritics (=letters with accents).

    Args:
        big_string (str): The string to search in
        sub_string (str): The string to search for

    Returns:
        bool: True if sub_string_x is found in big_string_x (ignoring diacritics), False otherwise
    """
    # Remove diacritics from both strings
    big_string_clean = remove_diacritics(text=big_string)
    sub_string_clean = remove_diacritics(text=sub_string)

    # Convert to lowercase for case-insensitive search
    big_string_clean = big_string_clean.lower()
    sub_string_clean = sub_string_clean.lower()

    # Check if sub_string appears in big_string
    return sub_string_clean in big_string_clean
