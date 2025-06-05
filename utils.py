"""Sanitize string, for file names and MP3 title."""

import re

# Regex: remove leading non-alphanumeric (English+Greek) characters, including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF]+')

def sanitize_string(dirty_string: str) -> str:
    """Remove leading unwanted characters (including spaces) from string."""
    return pattern.sub('', dirty_string)
