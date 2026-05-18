"""Read audio file tags and walk the library directory tree."""
import logging
import re
from collections.abc import Iterator
from pathlib import Path

import mutagen

from funcs_audio_tag_handlers import (
    AudioTagHandler, FLACTagHandler, M4ATagHandler, MP3TagHandler,
)
from funcs_check_greek_singles.models import Song, SongKey
from funcs_check_greek_singles.normalize import extract_year, normalize

AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.flac'}

# EasyID3 (mp3) registers 'date' which maps to TDRC; m4a uses Apple's atom; flac uses Vorbis 'date'.
DATE_KEY_BY_EXT: dict[str, str] = {
    'mp3': 'date',
    'm4a': '\xa9day',
    'flac': 'date',
}

MONTH_FOLDER_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])(\s+.+)?$')
MONTH_ARG_RE = re.compile(r'^(\d{4})(?:-(\d{2}))?$')

# Handler instances are stateless: build once and reuse across all files.
_HANDLERS_BY_EXT: dict[str, AudioTagHandler] = {
    'mp3': MP3TagHandler(),
    'm4a': M4ATagHandler(),
    'flac': FLACTagHandler(),
}

logger = logging.getLogger(__name__)


def _read_duration(file_path: Path) -> float:
    try:
        # mutagen.File is the documented public API; pyright's __all__ check is a false positive.
        audio = mutagen.File(file_path)  # type: ignore[attr-defined]
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug(f'mutagen.File raised for {file_path.name}: {exc}')
        return 0.0
    if audio is None or audio.info is None:
        return 0.0
    length = float(getattr(audio.info, 'length', 0.0) or 0.0)
    return length if length > 0 else 0.0


def read_song(file_path: Path) -> Song | None:
    """Parse a single audio file into a Song. Returns None for unsupported extensions."""
    ext = file_path.suffix.lower().lstrip('.')
    handler = _HANDLERS_BY_EXT.get(ext)
    if handler is None:
        return None
    try:
        audio = handler.open_audio_file(file_path=file_path)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(f'Failed to read tags from {file_path}: {exc}')
        return Song(
            file_path=file_path, raw_title='', raw_artist='', raw_album='',
            year='', duration_seconds=0.0, key=None,
        )
    raw_title = handler.get_tag(audio=audio, tag_name=handler.TAG_TITLE).strip()
    raw_artist = handler.get_tag(audio=audio, tag_name=handler.TAG_ARTIST).strip()
    raw_album = handler.get_tag(audio=audio, tag_name=handler.TAG_ALBUM).strip()
    date_value = handler.get_tag(audio=audio, tag_name=DATE_KEY_BY_EXT[ext]).strip()
    year = extract_year(date_tag_value=date_value)
    duration_seconds = _read_duration(file_path=file_path)

    norm_title = normalize(text=raw_title)
    norm_artist = normalize(text=raw_artist)
    key = SongKey(title=norm_title, artist=norm_artist) if norm_title and norm_artist else None
    return Song(
        file_path=file_path, raw_title=raw_title, raw_artist=raw_artist, raw_album=raw_album,
        year=year, duration_seconds=duration_seconds, key=key,
    )


def collect_songs(directory: Path, title_prefix_norm: str = '',
                  log_per_file: bool = False, progress_every: int = 0) -> list[Song]:
    """Scan a directory (flat, non-recursive) and return parsed Songs.

    When title_prefix_norm is non-empty, drops Songs whose normalized title
    does not startswith the prefix (and untagged Songs, which have no title).

    log_per_file=True logs each scanned file's name + raw title at DEBUG.
    progress_every>0 logs a 'Scanned N/total' line every N files at DEBUG.
    """
    songs: list[Song] = []
    candidates = [
        entry for entry in sorted(directory.iterdir())
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTENSIONS
    ]
    total = len(candidates)
    for idx, entry in enumerate(candidates, start=1):
        song = read_song(file_path=entry)
        if song is None:
            continue
        if log_per_file:
            display_title = song.raw_title or '(no title)'
            logger.debug(f'  {entry.name} -> {display_title}')
        if title_prefix_norm and (song.key is None or not song.key.title.startswith(title_prefix_norm)):
            continue
        songs.append(song)
        if progress_every > 0 and idx % progress_every == 0:
            logger.debug(f'  Scanned {idx}/{total} files in {directory.name}...')
    return songs


def iter_month_folders(by_month_root: Path,
                       start_yyyymm: str = '',
                       end_yyyymm: str = '') -> Iterator[Path]:
    """Yield immediate subdirectories of by_month_root whose name matches 'YYYY-MM[ suffix]'.

    start_yyyymm and end_yyyymm bound the inclusive month range; empty string disables
    that side. Comparison is lexicographic on the leading 'YYYY-MM' (zero-padded).
    """
    for entry in sorted(by_month_root.iterdir()):
        if not entry.is_dir():
            continue
        if not MONTH_FOLDER_RE.match(entry.name):
            logger.debug(f'Skipping non-month folder: {entry.name}')
            continue
        prefix = entry.name[:7]
        if start_yyyymm and prefix < start_yyyymm:
            continue
        if end_yyyymm and prefix > end_yyyymm:
            continue
        yield entry


def parse_month_arg(value: str, *, is_end: bool) -> str:
    """Validate and normalize a '--start-month'/'--end-month' CLI value to 'yyyy-mm'.

    Accepts 'yyyy-mm' (passed through after validation) or 'yyyy' (expanded to
    'yyyy-01' when is_end is False, 'yyyy-12' otherwise). Raises ValueError on any
    malformed input or month outside 01..12.
    """
    match = MONTH_ARG_RE.match(value)
    if not match:
        raise ValueError(f'Invalid month arg {value!r}: expected yyyy or yyyy-mm.')
    year_part, month_part = match.group(1), match.group(2)
    if month_part is None:
        month_part = '12' if is_end else '01'
    elif not '01' <= month_part <= '12':
        raise ValueError(f'Invalid month arg {value!r}: month component must be 01..12.')
    return f'{year_part}-{month_part}'
