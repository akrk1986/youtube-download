"""Pure string-normalization helpers. No I/O."""
import re

from funcs_utils import remove_diacritics

_NON_KEY_CHAR_RE = re.compile(r'[^\w\s]', re.UNICODE)
_WHITESPACE_RE = re.compile(r'\s+')
_YEAR_RE = re.compile(r'(\d{4})')


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, strip non-alphanumeric, collapse whitespace."""
    if not text:
        return ''
    stripped = remove_diacritics(text=text).lower()
    stripped = _NON_KEY_CHAR_RE.sub(' ', stripped)
    return _WHITESPACE_RE.sub(' ', stripped).strip()


def extract_year(date_tag_value: str) -> str:
    """Extract the first 4-digit run from a date tag value (year-only result)."""
    if not date_tag_value:
        return ''
    match = _YEAR_RE.search(date_tag_value)
    return match.group(1) if match else ''


def format_duration(seconds: float | None) -> str:
    """Format duration as 'm:ss' for <1h, 'h:mm:ss' for >=1h, '' for 0/None/negative."""
    if seconds is None or seconds <= 0:
        return ''
    total = int(round(seconds))
    if total >= 3600:
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f'{hours}:{minutes:02d}:{secs:02d}'
    minutes = total // 60
    secs = total % 60
    return f'{minutes}:{secs:02d}'


def missing_tag_fields(raw_title: str, raw_artist: str) -> list[str]:
    """Return the list of mandatory tag fields that are blank."""
    missing: list[str] = []
    if not raw_title:
        missing.append('title')
    if not raw_artist:
        missing.append('artist')
    return missing
