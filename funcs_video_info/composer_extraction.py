"""Extract the song composer from a Greek video description."""
import re

from common_av.text import remove_diacritics

# Credit labels. Each is a list so synonyms can be added as they are encountered
# (e.g. another word for 'music' or 'lyrics'). 'Μουσική' = music, 'Στίχοι' = lyrics.
MUSIC_LABELS = ['Μουσική']
LYRICS_LABELS = ['Στίχοι']

_WHITESPACE_RE = re.compile(r'\s+')


def _normalize(text: str) -> str:
    """Casefold and strip diacritics so labels match regardless of case/accents."""
    return remove_diacritics(text).casefold()


def _normalize_label(text: str) -> str:
    """Normalize a label and drop all its whitespace (so 'Μουσική / Στίχοι' matches)."""
    return _WHITESPACE_RE.sub('', _normalize(text))


def _build_allowed_labels() -> set[str]:
    """Build the set of accepted (normalized) credit labels.

    Accepts music alone, music/lyrics, and lyrics/music — the last two cover the
    case where the same person wrote both the music and the lyrics.

    Returns:
        set[str]: Normalized, whitespace-free labels that credit the composer.
    """
    music = {_normalize_label(label) for label in MUSIC_LABELS}
    lyrics = {_normalize_label(label) for label in LYRICS_LABELS}
    allowed = set(music)
    for mus in music:
        for lyr in lyrics:
            allowed.add(f'{mus}/{lyr}')
            allowed.add(f'{lyr}/{mus}')
    return allowed


_ALLOWED_LABELS = _build_allowed_labels()


def extract_composer_from_description(description: str) -> str | None:
    """Return the composer credited in a Greek video description, or None.

    Scans each line for a credit label before the first colon — one of music,
    music/lyrics, or lyrics/music (see MUSIC_LABELS / LYRICS_LABELS). Label
    matching is case- and diacritics-insensitive and tolerates whitespace around
    the words, slash, and colon. The name after the colon is captured up to the
    end of that line, with its original spacing and diacritics preserved.

    Args:
        description: Full video description text.

    Returns:
        str | None: The composer name, or None if no composer credit is present.
    """
    if not description:
        return None
    for line in description.splitlines():
        if ':' not in line:
            continue
        label, _, value = line.partition(':')
        if _normalize_label(label) in _ALLOWED_LABELS:
            composer = value.strip()
            if composer:
                return composer
    return None
