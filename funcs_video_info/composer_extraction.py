"""Extract the song composer from a Greek video description."""
import re

# Greek credit label: 'Μουσική:' or 'Μουσική/Στίχοι:' (music & lyrics by the same
# person). Whitespace around the slash and colon is tolerated; the captured name
# keeps its own internal spacing and runs to the end of that line.
_COMPOSER_RE = re.compile(r'Μουσική\s*(?:/\s*Στίχοι)?\s*:\s*(.+)')


def extract_composer_from_description(description: str) -> str | None:
    """Return the composer credited in a Greek video description, or None.

    Matches a 'Μουσική:' or 'Μουσική/Στίχοι:' label (whitespace around the
    slash/colon tolerated) and captures the name up to the end of that line.
    The '.+' never crosses a newline, so only the rest of the matched line is
    captured; surrounding whitespace is then trimmed.

    Args:
        description: Full video description text.

    Returns:
        str | None: The composer name with its internal spacing preserved, or
        None if no composer credit is present.
    """
    if not description:
        return None
    match = _COMPOSER_RE.search(description)
    if not match:
        return None
    composer = match.group(1).strip()
    return composer or None
