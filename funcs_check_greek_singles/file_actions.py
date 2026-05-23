"""Copy or move songs missing from 01-Singles-All into per-folder subdirs.

The cross-checker's `only_in_months` rows identify songs present under
`03-Singles-by-Month/<yyyy-mm[-suffix]>/` but absent from `01-Singles-All/`.
This module performs the optional copy/move action driven by the
`--missing-action` and `--target-is-year` flags. The action is prompted
interactively (cancel / all / numeric cap) and never runs without user input.
"""
import logging
import os
import re
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mutagen import MutagenError

from funcs_check_greek_singles.config import VERDICT_DUPLICATE, VERDICT_ORIGINAL
from funcs_check_greek_singles.models import InFolderDupMember, MatchedRow, StagingGroup
from funcs_check_greek_singles.report import _format_size
from funcs_check_greek_singles.state_tag import (
    VERDICT_AMBIGUOUS, VERDICT_PENDING,
    build_origin_marker, classify_verdict, clear_state, parse_origin, read_state, write_state,
)

logger = logging.getLogger(__name__)

Action = Literal['copy', 'move']

_AUDIO_SUFFIXES = {'.mp3', '.m4a', '.flac'}
_GROUP_DIR_RE = re.compile(r'grp-(\d+)$')


@dataclass(frozen=True)
class ActionSummary:
    """Outcome of apply_missing_action: counters surfaced to the user."""
    attempted: int
    succeeded: int
    failed: int
    skipped: int


def _target_folder_name(row: MatchedRow, *, target_is_year: bool) -> str:
    """Return the destination folder name under singles_all_root for a row."""
    folder = row.month_folder
    assert folder is not None, 'only_in_months rows always carry a month_folder'
    return folder[:4] if target_is_year else folder


def _target_style_label(*, target_is_year: bool) -> str:
    """Human-readable description of where the action will place files."""
    if target_is_year:
        return 'per-year subfolder under 01-Singles-All/ (All/<YYYY>/)'
    return 'per-month subfolder under 01-Singles-All/ (All/<YYYY-MM-...>/)'


def prompt_action_limit(*, action: Action, row_count: int, total_bytes: int,
                        target_is_year: bool) -> int | None:
    """Ask the user how many rows to process. Returns the limit, or None to cancel.

    Acceptable replies (case-insensitive, stripped):
      ''  / 'n'       -> None (cancel; safe default)
      'all'           -> row_count
      positive int N  -> min(N, row_count)
      anything else   -> re-prompt with an error message
    EOFError on input -> None
    """
    print(f"\nApply action '{action}' to {row_count} songs "
          f"({_format_size(size_bytes=total_bytes)})?")
    print(f"  Target style: {_target_style_label(target_is_year=target_is_year)}")
    prompt = "Reply 'n' to cancel, 'all' to process every file, or a number to cap the count: "
    while True:
        try:
            raw = input(prompt)
        except EOFError:
            return None
        reply = raw.strip().lower()
        if reply in ('', 'n'):
            return None
        if reply == 'all':
            return row_count
        try:
            value = int(reply)
        except ValueError:
            print("Invalid: reply 'n', 'all', or a positive integer.")
            continue
        if value <= 0:
            print('Invalid: N must be > 0.')
            continue
        return min(value, row_count)


def apply_missing_action(
        *,
        rows: list[MatchedRow],
        singles_all_root: Path,
        action: Action,
        target_is_year: bool,
        limit: int,
) -> ActionSummary:
    """Copy or move up to `limit` rows' files under singles_all_root / <folder>.

    Rows are sorted by filename before truncating to `limit`, so partial runs
    (limit < len(rows)) always start from the alphabetical head.
    Folder name follows _target_folder_name(). Existing targets are overwritten.
    Per-file OSError is logged and counted as `failed`; the loop continues.
    Missing source files are counted as `skipped`. limit > len(rows) is fine
    (treated as 'process all').
    """
    sorted_rows = sorted(rows, key=lambda r: Path(r.file_path).name)
    attempted = succeeded = failed = skipped = 0
    for row in sorted_rows[:limit]:
        attempted += 1
        src = Path(row.file_path)
        if not src.is_file():
            logger.warning(f'Source file missing, skipping: {src}')
            skipped += 1
            continue
        target_dir = singles_all_root / _target_folder_name(
            row=row, target_is_year=target_is_year)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / src.name
            if action == 'copy':
                shutil.copy2(src=src, dst=dst)
            else:
                if dst.exists():
                    dst.unlink()
                shutil.move(src=str(src), dst=str(dst))
            logger.info(f'{action}: {src.name} -> {target_dir.name}/')
            succeeded += 1
        except OSError as exc:
            logger.warning(f'{action} failed for {src.name}: {exc}')
            failed += 1
    return ActionSummary(
        attempted=attempted, succeeded=succeeded, failed=failed, skipped=skipped)


@dataclass(frozen=True)
class StageSummary:
    """Outcome of stage_duplicates: counters surfaced to the user."""
    attempted: int
    staged: int
    skipped: int
    failed: int


@dataclass(frozen=True)
class InspectSummary:
    """Outcome of process_inspected: per-verdict counters surfaced to the user."""
    moved_to_dupes: int
    restored: int
    pending: int
    ambiguous: int
    no_marker: int
    failed: int


def _iter_audio_files(directory: Path) -> Iterator[Path]:
    """Yield mp3/m4a/flac files directly under directory (case-insensitive), name-sorted."""
    if not directory.is_dir():
        return
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if entry.is_file() and entry.suffix.lower() in _AUDIO_SUFFIXES:
            yield entry


def _unique_dest(dest_dir: Path, name: str) -> Path:
    """Return a non-colliding path in dest_dir for name, appending ' (N)' if needed."""
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while True:
        candidate = dest_dir / f'{stem} ({counter}){suffix}'
        if not candidate.exists():
            return candidate
        counter += 1


def _move_preserving_mtime(src: Path, dst: Path) -> None:
    """Move src to dst (which must not exist), preserving the original mtime."""
    before = src.stat()
    shutil.move(str(src), str(dst))
    os.utime(dst, (before.st_atime, before.st_mtime))


def _group_dirs(staging_dir: Path, group_range: tuple[int, int] | None) -> list[Path]:
    """Return staging_dir's grp-NNNN subfolders, number-sorted.

    With group_range=(lo, hi), only folders whose number is in the inclusive range
    are returned (numbers absent from disk are simply skipped).
    """
    if not staging_dir.is_dir():
        return []
    numbered: list[tuple[int, Path]] = []
    for entry in staging_dir.iterdir():
        match = _GROUP_DIR_RE.fullmatch(entry.name) if entry.is_dir() else None
        if match is None:
            continue
        number = int(match.group(1))
        if group_range is not None and not group_range[0] <= number <= group_range[1]:
            continue
        numbered.append((number, entry))
    return [path for _, path in sorted(numbered)]


def _remove_if_empty(directory: Path, dry_run: bool) -> None:
    """Remove a group folder once it has no entries left (no-op on dry-run)."""
    if dry_run:
        return
    try:
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            logger.info(f'removed empty group folder: {directory.name}')
    except OSError as exc:
        logger.warning(f'could not remove {directory.name}: {exc}')


def next_group_number(staging_dir: Path) -> int:
    """Return the next free group number: (highest existing grp-NNNN) + 1, else 1.

    Lets a re-stage append new groups after any un-processed leftovers instead of
    colliding with them.
    """
    highest = 0
    if staging_dir.is_dir():
        for entry in staging_dir.iterdir():
            match = _GROUP_DIR_RE.fullmatch(entry.name) if entry.is_dir() else None
            if match is not None:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def parse_group_range(value: str) -> tuple[int, int]:
    """Parse a '--staging-groups N1,N2' value into an inclusive (lo, hi) range.

    Raises ValueError unless it is two positive integers with N1 <= N2.
    """
    parts = value.split(',')
    if len(parts) != 2:
        raise ValueError("--staging-groups must be 'N1,N2' (two integers, e.g. 7,10).")
    try:
        lo, hi = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f'--staging-groups expects integers, got {value!r}.') from exc
    if lo < 1 or hi < 1:
        raise ValueError('--staging-groups numbers must be >= 1.')
    if lo > hi:
        raise ValueError(f'--staging-groups start ({lo}) is greater than end ({hi}).')
    return lo, hi


def cluster_is_fully_judged(members: tuple[InFolderDupMember, ...]) -> bool:
    """True if every cluster member already carries the 'original' verdict.

    Such a cluster was fully resolved by the user (all kept as distinct versions),
    so staging skips it. A cluster with any non-'original' member (a new or
    unmarked file) is staged in full, so the newcomer can be compared against the
    existing versions.
    """
    return all(
        classify_verdict(read_state(file_path=Path(member.file_path), field='verdict'))
        == VERDICT_ORIGINAL
        for member in members
    )


def stage_duplicates(*, groups: list[StagingGroup], root: Path, staging_dir: Path,
                     dry_run: bool) -> StageSummary:
    """Move each dupe group into its own Staging-Dupes/grp-NNNN subfolder.

    For each member the script writes the 'DUPE-ORIGIN[<path relative to root>]'
    marker into the Album Artist tag (it never touches the verdict/Copyright field
    — only the user does), then moves the file into the group's subfolder under a
    '<parent-folder> — <name>' name (uniquified on collision). The tag, not the
    staged name, is authoritative for restore. mtime is preserved across the tag
    write and the move. dry_run only logs intended moves.
    """
    attempted = staged = skipped = failed = 0
    for group in groups:
        group_dir = staging_dir / group.folder_name
        if not dry_run:
            group_dir.mkdir(parents=True, exist_ok=True)
        for member in group.members:
            attempted += 1
            src = Path(member.file_path)
            if not src.is_file():
                logger.warning(f'Source missing, skipping: {src}')
                skipped += 1
                continue
            try:
                rel = src.relative_to(root).as_posix()
            except ValueError:
                logger.warning(f'File is not under root, skipping: {src}')
                skipped += 1
                continue
            dst = _unique_dest(dest_dir=group_dir, name=f'{src.parent.name} — {src.name}')
            if dry_run:
                logger.info(f'[dry-run] stage: {rel} -> {group.folder_name}/{dst.name}')
                staged += 1
                continue
            try:
                write_state(file_path=src, value=build_origin_marker(origin_relpath=rel),
                            field='origin')
                _move_preserving_mtime(src=src, dst=dst)
                logger.info(f'stage: {rel} -> {group.folder_name}/{dst.name}')
                staged += 1
            except (OSError, MutagenError) as exc:
                logger.warning(f'stage failed for {src.name}: {exc}')
                failed += 1
    return StageSummary(attempted=attempted, staged=staged, skipped=skipped, failed=failed)


def _restore_to_origin(*, src: Path, origin: str, root: Path, dry_run: bool) -> bool:
    """Move an 'original' file back to root/<origin> and clear its origin marker.

    The verdict (Copyright) is left untouched so 'original' persists — the script
    never modifies the verdict. Returns True on success.
    """
    dst = root / origin
    if dst.exists():
        logger.warning(f'restore target already exists, skipping: {origin}')
        return False
    if dry_run:
        logger.info(f'[dry-run] restore -> {origin}: {src.name}')
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    _move_preserving_mtime(src=src, dst=dst)
    clear_state(file_path=dst, field='origin')
    logger.info(f'restore -> {origin}')
    return True


def _route_inspected_file(*, src: Path, root: Path, dupes_dir: Path, dry_run: bool) -> str:
    """Act on one staged file by its verdict; return an outcome key for counting.

    Outcome is one of: 'moved_to_dupes', 'restored', 'pending', 'ambiguous',
    'no_marker', 'failed'.
    """
    origin = parse_origin(value=read_state(file_path=src, field='origin'))
    if origin is None:
        logger.warning(f'no DUPE-ORIGIN marker, skipping: {src.name}')
        return 'no_marker'
    verdict = classify_verdict(value=read_state(file_path=src, field='verdict'))
    if verdict == VERDICT_DUPLICATE:
        dst = _unique_dest(dest_dir=dupes_dir, name=src.name)
        if dry_run:
            logger.info(f'[dry-run] duplicate -> {dupes_dir.name}/{dst.name}: {src.name}')
        else:
            dupes_dir.mkdir(parents=True, exist_ok=True)
            _move_preserving_mtime(src=src, dst=dst)
            logger.info(f'duplicate -> {dupes_dir.name}/{dst.name}')
        return 'moved_to_dupes'
    if verdict == VERDICT_ORIGINAL:
        return 'restored' if _restore_to_origin(
            src=src, origin=origin, root=root, dry_run=dry_run) else 'failed'
    if verdict == VERDICT_PENDING:
        logger.info(f'pending (awaiting verdict): {src.name}')
        return 'pending'
    if verdict == VERDICT_AMBIGUOUS:
        logger.warning(f'ambiguous verdict, skipping: {src.name}')
        return 'ambiguous'
    logger.warning(f'unexpected verdict {verdict!r}, skipping: {src.name}')
    return 'failed'


def process_inspected(*, staging_dir: Path, root: Path, dupes_dir: Path,
                      group_range: tuple[int, int] | None, dry_run: bool) -> InspectSummary:
    """Act on inspected files in the selected grp-NNNN folders by Copyright verdict.

    'duplicate' -> move to dupes_dir; 'original' -> restore to root/<origin>
    (clearing only the origin marker; the verdict persists); pending / ambiguous /
    no-marker are reported and left in place. group_range=(lo, hi) limits to those
    group folders (all if None). A group folder is removed once it is empty. mtime
    preserved; dry_run only logs.
    """
    counts = {'moved_to_dupes': 0, 'restored': 0, 'pending': 0,
              'ambiguous': 0, 'no_marker': 0, 'failed': 0}
    for group_dir in _group_dirs(staging_dir=staging_dir, group_range=group_range):
        for src in _iter_audio_files(directory=group_dir):
            try:
                outcome = _route_inspected_file(src=src, root=root, dupes_dir=dupes_dir,
                                                dry_run=dry_run)
            except (OSError, MutagenError) as exc:
                logger.warning(f'inspect failed for {src.name}: {exc}')
                outcome = 'failed'
            counts[outcome] += 1
        _remove_if_empty(directory=group_dir, dry_run=dry_run)
    return InspectSummary(**counts)


def unstage_all(*, staging_dir: Path, root: Path,
                group_range: tuple[int, int] | None, dry_run: bool) -> InspectSummary:
    """Move staged files back to their origin, ignoring the verdict (abort staging).

    Reads each file's DUPE-ORIGIN marker and restores it to root/<origin>, clearing
    only the marker and leaving the verdict (Copyright) untouched. group_range
    limits to those grp-NNNN folders (all if None); emptied folders are removed.
    mtime preserved; dry_run only logs.
    """
    restored = no_marker = failed = 0
    for group_dir in _group_dirs(staging_dir=staging_dir, group_range=group_range):
        for src in _iter_audio_files(directory=group_dir):
            try:
                origin = parse_origin(value=read_state(file_path=src, field='origin'))
                if origin is None:
                    logger.warning(f'no DUPE-ORIGIN marker, skipping: {src.name}')
                    no_marker += 1
                elif _restore_to_origin(src=src, origin=origin, root=root, dry_run=dry_run):
                    restored += 1
                else:
                    failed += 1
            except (OSError, MutagenError) as exc:
                logger.warning(f'unstage failed for {src.name}: {exc}')
                failed += 1
        _remove_if_empty(directory=group_dir, dry_run=dry_run)
    return InspectSummary(moved_to_dupes=0, restored=restored, pending=0,
                          ambiguous=0, no_marker=no_marker, failed=failed)
