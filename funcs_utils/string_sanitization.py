"""String and filename sanitization utilities."""
import re

import emoji
from common_av.text import remove_diacritics

from project_defs import LEADING_NONALNUM_PATTERN, MAX_FILENAME_LENGTH, MULTIPLE_SPACES_PATTERN

# Regex: remove leading non-alphanumeric characters (English+Greek+Hebrew+French+Turkish), including spaces
pattern = re.compile(LEADING_NONALNUM_PATTERN)

# Subtitle files written by yt-dlp are named '<stem>.<lang>.<ext>' (e.g. 'Title.el.srt')
SUBTITLE_EXTENSIONS = {'srt', 'vtt', 'ass'}
# Language tag of a subtitle file: 'el', 'en-US', 'pt-BR', 'zh-Hans' (primary subtag lowercase)
SUBTITLE_LANG_PATTERN = re.compile(r'^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$')

# File extensions kept as extensions (compared case-insensitively); any other suffix is part of the name
VALID_EXTENSIONS = {'mp4', 'wmv', 'mkv', 'mp3', 'm4a', 'flac', 'webm', 'avi', 'mov', 'txt'} | SUBTITLE_EXTENSIONS
# ASCII punctuation kept in a file name (ASCII letters and digits are always kept)
_ALLOWED_ASCII_PUNCTUATION = ' .,;!()-_[]{}'
# Latin Extended-A letters kept: French ligatures and Turkish İ, ı, Ğ, ğ, Ş, ş, among others
# noinspection SpellCheckingInspection
_ALLOWED_LATIN_EXTENDED_A = ('ĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁł'
                             'ŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž')
# Any character not kept in a file name (replaced with a space). Kept: ASCII letters, digits and
# _ALLOWED_ASCII_PUNCTUATION; Greek (U+0370-U+03FF); Hebrew letters (U+05D0-U+05EA); Latin-1 Supplement
# U+00C0-U+00FF (French accents, Turkish Ö, Ü, Ç - and also the symbols × and ÷); and _ALLOWED_LATIN_EXTENDED_A
_DISALLOWED_CHARS = re.compile(f'[^A-Za-z0-9{re.escape(_ALLOWED_ASCII_PUNCTUATION)}'
                               f'\u0370-\u03ff\u05d0-\u05ea\u00c0-\u00ff{_ALLOWED_LATIN_EXTENDED_A}]')
# Characters removed from the end of a name cut to fit the length limit, so it does not end in a
# separator or an opening bracket ('Title..mp4', 'Title (.mp4'); a trailing '.' is also dropped by Windows
_CUT_TRAILING_CHARS = ' .,;-_([{'


def _split_extension(file_name: str) -> tuple[str, str, str]:
    """Split a file name into its name part, a supported extension, and a subtitle language tag.

    The extension is split off only when it is in ``VALID_EXTENSIONS``; otherwise the whole string is the
    name part. A subtitle file's language tag ('Title.el.srt' → 'el') is split off as well.

    Args:
        file_name: The file name to split.

    Returns:
        tuple[str, str, str]: The name part, the extension ('' when none), and the language tag ('' when none).
    """
    if '.' not in file_name:
        return file_name, '', ''
    name_part, extension = file_name.rsplit('.', 1)
    if extension.lower() not in VALID_EXTENSIONS:
        return file_name, '', ''
    if extension.lower() in SUBTITLE_EXTENSIONS and '.' in name_part:
        stem, candidate_tag = name_part.rsplit('.', 1)
        if SUBTITLE_LANG_PATTERN.match(candidate_tag):
            return stem, extension, candidate_tag
    return name_part, extension, ''


def sanitize_string(dirty_string: str) -> str:
    """
    Sanitize filename by:
    1. Replacing emojis with spaces
    2. Replacing foreign characters (not English/French/Greek/Hebrew/Turkish) with spaces
    3. Removing leading unwanted characters and spaces
    4. Compressing multiple spaces into one
    5. Removing trailing spaces before file extension
    6. Cutting the name to MAX_FILENAME_LENGTH, without leaving a separator or an opening bracket at the cut

    Subtitle files keep their language tag ('Title.el.srt'), and their stem is truncated to the same
    length as a media file's, so the subtitle still pairs with its video after the rename.
    """
    if not dirty_string:
        return dirty_string

    # Split off a supported extension (and a subtitle's language tag); anything else stays in the name
    name_part, extension, lang_tag = _split_extension(file_name=dirty_string)

    # 1. Replace all emojis with spaces
    name_part = emoji.replace_emoji(name_part, replace=' ')

    # 2. Replace foreign characters (not English/French/Greek/Hebrew/Turkish) with spaces
    name_part = _DISALLOWED_CHARS.sub(' ', name_part)

    # 3. Remove leading unwanted characters (using existing pattern)
    name_part = pattern.sub('', name_part)

    # 4. Compress multiple spaces into one
    name_part = re.sub(MULTIPLE_SPACES_PATTERN, ' ', name_part)

    # 5. Remove leading and trailing spaces
    name_part = name_part.strip()

    # 6. Truncate to ensure total filename length <= MAX_FILENAME_LENGTH characters (the dot and extension count)
    max_name_length = MAX_FILENAME_LENGTH - 1 - len(extension) if extension else MAX_FILENAME_LENGTH
    if len(name_part) > max_name_length:
        name_part = name_part[:max_name_length].rstrip(_CUT_TRAILING_CHARS)

    if not extension:
        return name_part
    # Reconstruct filename (the language tag sits outside the length budget, keeping the stem aligned with the video)
    if lang_tag:
        extension = f'{lang_tag}.{extension}'
    return f'{name_part or 'untitled'}.{extension}'


def greek_search(big_string: str, sub_string: str) -> bool:
    """
    Check if sub_string appears in big_string (case-insensitive), ignoring Greek diacritics (=letters with accents).

    Args:
        big_string: The string to search in
        sub_string: The string to search for

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
