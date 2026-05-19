"""Copy or move songs missing from 01-Singles-All into per-folder subdirs.

The cross-checker's `only_in_months` rows identify songs present under
`03-Singles-by-Month/<yyyy-mm[-suffix]>/` but absent from `01-Singles-All/`.
This module performs the optional copy/move action driven by the
`--missing-action` and `--target-is-year` flags. The action is prompted
interactively (cancel / all / numeric cap) and never runs without user input.
"""
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from funcs_check_greek_singles.models import MatchedRow
from funcs_check_greek_singles.report import _format_size

logger = logging.getLogger(__name__)

Action = Literal['copy', 'move']


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
