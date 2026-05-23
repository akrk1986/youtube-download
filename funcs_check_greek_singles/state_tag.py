"""Read/write/clear the dupe-workflow state across two standard tag fields.

The state is split over two fields, both shown as columns and editable in mp3tag
and tagscan, mutagen-readable, and present in mp3/m4a/flac:

- **origin** — the Album Artist tag (ID3 ``TPE2`` / MP4 ``aART`` / Vorbis
  ``ALBUMARTIST``). The script writes ``DUPE-ORIGIN[<path relative to --root>]``
  here at staging and clears it on restore. (This library fills Album Artist
  redundantly = Artist, so repurposing it loses no real information.)
- **verdict** — the Copyright tag (ID3 ``TCOP`` / MP4 ``cprt`` / Vorbis
  ``COPYRIGHT``). The *user* types ``duplicate`` or ``original`` here during
  inspection; the script only ever reads it and never writes it. ``original``
  persists on the file.

Keeping them in separate fields means the user edits a short, clean verdict
column without ever touching the long origin path. To move either field, change
its entry in ``_FIELDS`` (and, for mp3, the frame in ``_write_field``).

All writes preserve the file's mtime (the library values original timestamps).
"""
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError, TCOP, TPE2
from mutagen.mp4 import MP4

from funcs_check_greek_singles.config import (
    STATE_TAG_MARKER, VERDICT_DUPLICATE, VERDICT_ORIGINAL,
)

_UTF16 = 1  # ID3 text encoding; matches the project's Greek-text handling.

Field = Literal['origin', 'verdict']

# Verdict classifications returned by classify_verdict beyond the two user tokens.
VERDICT_PENDING = 'pending'        # verdict field empty -> not inspected yet
VERDICT_AMBIGUOUS = 'ambiguous'    # verdict field holds unrecognized text

# DUPE-ORIGIN[<origin>]. Greedy inside [] so the path may contain spaces.
_MARKER_RE = re.compile(rf'{re.escape(STATE_TAG_MARKER)}\[(?P<origin>.*)\]',
                        re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class _FieldSpec:
    """Per-container tag keys for one logical state field."""
    id3_key: str
    mp4_key: str
    flac_key: str


_FIELDS: dict[str, _FieldSpec] = {
    'origin': _FieldSpec(id3_key='TPE2', mp4_key='aART', flac_key='albumartist'),
    'verdict': _FieldSpec(id3_key='TCOP', mp4_key='cprt', flac_key='copyright'),
}


def _read_field(file_path: Path, spec: _FieldSpec) -> str:
    """Return the tag value for spec in a supported file, or '' if absent."""
    suffix = file_path.suffix.lower()
    if suffix == '.mp3':
        try:
            id3 = ID3(file_path)
        except ID3NoHeaderError:
            return ''
        frames = id3.getall(spec.id3_key)
        return str(frames[0].text[0]) if frames and frames[0].text else ''
    if suffix == '.m4a':
        audio = MP4(file_path)
        if audio.tags is None:
            return ''
        values = audio.get(spec.mp4_key, [])
        return str(values[0]) if values else ''
    if suffix == '.flac':
        flac = FLAC(file_path)
        if flac.tags is None:
            return ''
        values = flac.get(spec.flac_key, [])
        return str(values[0]) if values else ''
    raise ValueError(f'Unsupported file type for state tag: {file_path.name}')


def _write_field(file_path: Path, spec: _FieldSpec, value: str) -> None:
    """Set the tag for spec to value in a supported file (no mtime handling)."""
    suffix = file_path.suffix.lower()
    if suffix == '.mp3':
        try:
            id3 = ID3(file_path)
        except ID3NoHeaderError:
            id3 = ID3()
        if spec.id3_key == 'TPE2':
            id3.setall('TPE2', [TPE2(encoding=_UTF16, text=[value])])
        else:
            id3.setall('TCOP', [TCOP(encoding=_UTF16, text=[value])])
        id3.save(file_path, v2_version=3)
        return
    if suffix == '.m4a':
        audio = MP4(file_path)
        if audio.tags is None:
            audio.add_tags()
        audio[spec.mp4_key] = [value]
        audio.save()
        return
    if suffix == '.flac':
        flac = FLAC(file_path)
        if flac.tags is None:
            flac.add_tags()
        flac[spec.flac_key] = [value]
        flac.save()
        return
    raise ValueError(f'Unsupported file type for state tag: {file_path.name}')


def _clear_field(file_path: Path, spec: _FieldSpec) -> None:
    """Remove the tag for spec from a supported file (no mtime handling)."""
    suffix = file_path.suffix.lower()
    if suffix == '.mp3':
        try:
            id3 = ID3(file_path)
        except ID3NoHeaderError:
            return
        if id3.getall(spec.id3_key):
            id3.delall(spec.id3_key)
            id3.save(file_path, v2_version=3)
        return
    if suffix == '.m4a':
        audio = MP4(file_path)
        if audio.tags is not None and spec.mp4_key in audio:
            del audio[spec.mp4_key]
            audio.save()
        return
    if suffix == '.flac':
        flac = FLAC(file_path)
        if flac.tags is not None and spec.flac_key in flac:
            del flac[spec.flac_key]
            flac.save()
        return
    raise ValueError(f'Unsupported file type for state tag: {file_path.name}')


def _run_preserving_mtime(file_path: Path, action: Callable[[], None]) -> None:
    """Run action(), then restore file_path's original access/modification times."""
    before = file_path.stat()
    action()
    os.utime(file_path, (before.st_atime, before.st_mtime))


def read_state(file_path: Path, *, field: Field) -> str:
    """Return the raw value of the given state field ('origin' or 'verdict')."""
    return _read_field(file_path=file_path, spec=_FIELDS[field])


def write_state(file_path: Path, value: str, *, field: Field) -> None:
    """Write value into the given state field, preserving the file's mtime."""
    _run_preserving_mtime(
        file_path=file_path,
        action=lambda: _write_field(file_path=file_path, spec=_FIELDS[field], value=value),
    )


def clear_state(file_path: Path, *, field: Field) -> None:
    """Remove the given state field, preserving the file's mtime."""
    _run_preserving_mtime(
        file_path=file_path,
        action=lambda: _clear_field(file_path=file_path, spec=_FIELDS[field]),
    )


def build_origin_marker(origin_relpath: str) -> str:
    """Return the origin marker for a path relative to --root."""
    return f'{STATE_TAG_MARKER}[{origin_relpath}]'


def parse_origin(value: str) -> str | None:
    """Extract the origin path from a DUPE-ORIGIN[...] marker, or None if absent."""
    match = _MARKER_RE.search(value or '')
    return match.group('origin').strip() if match else None


def classify_verdict(value: str) -> str:
    """Map a verdict-field value to a verdict constant.

    Empty -> VERDICT_PENDING; the text must equal a verdict token exactly
    (case-insensitive, trimmed) to count as VERDICT_ORIGINAL / VERDICT_DUPLICATE;
    anything else (e.g. "not a duplicate") is VERDICT_AMBIGUOUS, so a file is never
    moved on fuzzy text.
    """
    text = (value or '').strip().lower()
    if not text:
        return VERDICT_PENDING
    if text == VERDICT_ORIGINAL:
        return VERDICT_ORIGINAL
    if text == VERDICT_DUPLICATE:
        return VERDICT_DUPLICATE
    return VERDICT_AMBIGUOUS
