"""Greek strings handling, for file names and MP3 title."""
import re
import unicodedata

# Regex: remove leading non-alphanumeric (English+Greek) characters, including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF]+')

def sanitize_string(dirty_string: str) -> str:
    """Remove leading unwanted characters (including spaces) from string."""
    return pattern.sub('', dirty_string)

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
    Check if sub_string appears in big_string, ignoring Greek diacritics.

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
