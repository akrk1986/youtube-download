"""Load staged dupe groups for interactive inspection and build a cover-art collage.

Backs ``Utils/main-inspect-dupe-groups.py``. Given a range of
``Staging-Dupes/grp-NNNN/`` folders (selected with the same logic
``--post-inspection`` uses, so the inspected set matches the routed set), this
module parses every file into a :class:`InspectFile` -- carrying its tags, whether
it has embedded cover art, and its current verdict -- groups them per folder
(:class:`InspectGroup`, labelled A, B, C, ...), and can render a labelled
thumbnail grid (one row per group) to a PNG for at-a-glance comparison.

The verdict itself is written by the thin :func:`set_verdict` / cleared by the
caller via ``state_tag.clear_state``; this module never moves files -- routing
stays with ``--post-inspection``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp4 import MP4

from funcs_check_greek_singles.audio_reader import collect_songs
from funcs_check_greek_singles.file_actions import _group_dirs
from funcs_check_greek_singles.models import Song
from funcs_check_greek_singles.state_tag import (
    classify_verdict, read_deletion_tags, read_state, write_state,
)

if TYPE_CHECKING:
    from PIL.Image import Image
    from PIL.ImageDraw import ImageDraw
    from PIL.ImageFont import FreeTypeFont, ImageFont

logger = logging.getLogger(__name__)

# Common label fonts to try before falling back to Pillow's built-in bitmap font.
# Labels are ASCII ('1-A1'), so the default font is an acceptable last resort.
_FONT_CANDIDATES = ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf')


@dataclass(frozen=True)
class InspectFile:
    """One staged file: its parsed tags, cover-art bytes, label and current verdict."""
    path: Path
    label: str                  # 'A1', 'A2', 'B1', ... (group letter + 1-based index)
    group_name: str             # 'grp-0008'
    song: Song
    composer: str               # the file's composer tag (TCOM / ©wrt / composer), '' if absent
    comment: str                # the file's comment tag (COMM / ©cmt / comment), '' if absent
    art: bytes | None           # embedded cover-art bytes, or None if the file has none
    current_verdict: str        # classify_verdict() of the file's Copyright tag

    @property
    def has_art(self) -> bool:
        """True if the file carries embedded cover art."""
        return self.art is not None


@dataclass(frozen=True)
class InspectGroup:
    """One grp-NNNN folder's files, labelled with a single group letter."""
    name: str                   # 'grp-0008'
    letter: str                 # 'A', 'B', ...
    files: tuple[InspectFile, ...]


def _group_letter(index: int) -> str:
    """Return the spreadsheet-style letter for a 0-based group index (A..Z, AA, AB...)."""
    letters = ''
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord('A') + remainder) + letters
    return letters


def _load_font(size: int) -> FreeTypeFont | ImageFont:
    """Return a Pillow font at the given size, trying TrueType fonts then the default."""
    from PIL import ImageFont as pil_font  # pylint: disable=import-outside-toplevel
    for name in _FONT_CANDIDATES:
        try:
            return pil_font.truetype(name, size)
        except OSError:
            continue
    return pil_font.load_default(size=size)


def _draw_cell(*, canvas: Image, draw: ImageDraw, file: InspectFile,
               font: FreeTypeFont | ImageFont, box: tuple[int, int],
               cell_px: int, label_h: int, flat_index: int) -> None:
    """Draw one collage cell (thumbnail or empty box) plus its '<n>-<label>' caption."""
    from PIL import Image as pil_image, ImageOps as pil_ops  # pylint: disable=import-outside-toplevel
    box_x, box_y = box
    if file.art is not None:
        try:
            thumb = pil_image.open(BytesIO(file.art)).convert('RGB')
            # Crop-to-fill so the art covers the whole cell (no internal margins,
            # and small art is scaled up). Album art is square, so nothing is lost.
            thumb = pil_ops.fit(thumb, (cell_px, cell_px))
            canvas.paste(thumb, (box_x, box_y))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug(f'thumbnail failed for {file.path.name}: {exc}')
            draw.rectangle((box_x, box_y, box_x + cell_px, box_y + cell_px),
                           outline=(200, 0, 0), width=2)
    else:
        draw.rectangle((box_x, box_y, box_x + cell_px, box_y + cell_px),
                       outline=(160, 160, 160), width=2)

    caption = f'{flat_index}-{file.label}'
    text_y = box_y + cell_px + (label_h // 4)
    bbox = draw.textbbox((0, 0), caption, font=font)
    text_x = box_x + (cell_px - (bbox[2] - bbox[0])) // 2
    draw.text((text_x, text_y), caption, fill=(0, 0, 0), font=font)


def read_cover_art(path: Path) -> bytes | None:
    """Return the first embedded cover-art image bytes, or None if absent/unreadable.

    Handles the three supported containers (mp3 APIC, m4a covr, flac picture). Any
    read error is logged at debug and treated as 'no art' so inspection never aborts.
    """
    suffix = path.suffix.lower()
    try:
        if suffix == '.mp3':
            try:
                id3 = ID3(path)
            except ID3NoHeaderError:
                return None
            frames = id3.getall('APIC')
            return bytes(frames[0].data) if frames else None
        if suffix == '.m4a':
            audio = MP4(path)
            if audio.tags is None:
                return None
            covers = audio.tags.get('covr')
            return bytes(covers[0]) if covers else None
        if suffix == '.flac':
            pictures = FLAC(path).pictures
            return bytes(pictures[0].data) if pictures else None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug(f'cover-art read failed for {path.name}: {exc}')
    return None


def _read_composer_comment(path: Path) -> tuple[str, str]:
    """Return the file's (composer, comment) tags, each '' if absent/unreadable."""
    try:
        tags = read_deletion_tags(file_path=path)
        return tags.get('composer', ''), tags.get('comment', '')
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug(f'composer/comment read failed for {path.name}: {exc}')
        return '', ''


def load_groups(staging_dir: Path, group_range: tuple[int, int]) -> list[InspectGroup]:
    """Parse the selected grp-NNNN folders into labelled InspectGroups.

    Folders are chosen by file_actions._group_dirs (the exact selection
    --post-inspection routes), number-sorted. Within each folder files are parsed
    name-sorted by collect_songs; the group gets a letter (A, B, ...) and each file a
    '<letter><n>' label, its cover art, and its current verdict.
    """
    groups: list[InspectGroup] = []
    for group_index, group_dir in enumerate(_group_dirs(staging_dir=staging_dir,
                                                         group_range=group_range)):
        letter = _group_letter(index=group_index)
        files: list[InspectFile] = []
        for file_index, song in enumerate(collect_songs(directory=group_dir), start=1):
            verdict = classify_verdict(value=read_state(file_path=song.file_path, field='verdict'))
            composer, comment = _read_composer_comment(path=song.file_path)
            files.append(InspectFile(
                path=song.file_path,
                label=f'{letter}{file_index}',
                group_name=group_dir.name,
                song=song,
                composer=composer,
                comment=comment,
                art=read_cover_art(path=song.file_path),
                current_verdict=verdict,
            ))
        groups.append(InspectGroup(name=group_dir.name, letter=letter, files=tuple(files)))
    return groups


def iter_files(groups: list[InspectGroup]) -> list[InspectFile]:
    """Flatten the groups into a single inspection-ordered list of files."""
    return [file for group in groups for file in group.files]


def set_verdict(file_path: Path, verdict: str) -> None:
    """Write a verdict token into the file's Copyright tag, preserving its mtime.

    Pass the canonical VERDICT_ORIGINAL / VERDICT_DUPLICATE constants.
    """
    write_state(file_path=file_path, value=verdict, field='verdict')


def build_collage(groups: list[InspectGroup], out_path: Path, *,
                  cell_px: int = 220, pad: int = 8) -> Path:
    """Render a labelled cover-art grid (one row per group) to a PNG and return its path.

    Each group folder is its own row, with a thin divider between groups so the
    groupings stay visible. Within a row, cells show the file's cover art cropped to
    fill a cell_px square (an outlined box when the file has no art) with the flat
    label (e.g. '1-A1') beneath. The canvas is as wide as the largest group; shorter
    groups leave trailing empty cells. Requires Pillow; raises RuntimeError with a
    clear message if it is missing.
    """
    try:
        from PIL import Image as pil_image, ImageDraw as pil_draw  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError('Pillow is required to build the cover-art collage '
                           '(pip install Pillow).') from exc

    rows = [group.files for group in groups]
    max_cols = max((len(row) for row in rows), default=0)
    if max_cols == 0:
        raise RuntimeError('no files to render in the collage')

    label_h = 22
    cell_w = cell_px + pad
    cell_h = cell_px + label_h + pad
    canvas = pil_image.new('RGB', (max_cols * cell_w + pad, len(rows) * cell_h + pad),
                           color=(245, 245, 245))
    draw = pil_draw.Draw(canvas)
    font = _load_font(size=16)

    flat_index = 0
    for row_no, row in enumerate(rows):
        if row_no > 0:
            divider_y = pad + row_no * cell_h - pad // 2
            draw.line((pad, divider_y, canvas.width - pad, divider_y),
                      fill=(210, 210, 210), width=1)
        for col_no, file in enumerate(row):
            flat_index += 1
            _draw_cell(canvas=canvas, draw=draw, file=file, font=font,
                       box=(pad + col_no * cell_w, pad + row_no * cell_h),
                       cell_px=cell_px, label_h=label_h, flat_index=flat_index)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    logger.info(f'collage written: {out_path}')
    return out_path
