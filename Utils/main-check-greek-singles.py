#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
Cross-check the Greek singles library: report songs missing from one side
(01-Singles-All vs 03-Singles-by-Month/<yyyy-mm>) and songs that appear in
multiple month folders. Implementation lives in funcs_check_greek_singles/.

Run with --help for usage; --version for the build timestamp.
"""
import argparse
import logging
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from rich.console import Console  # noqa: E402

from funcs_check_greek_singles.audio_reader import (  # noqa: E402
    collect_songs, iter_month_folders, parse_month_arg,
)
from funcs_check_greek_singles.database import (  # noqa: E402
    SIDE_MONTH, SIDE_SINGLES_ALL,
    init_db, insert_song,
    query_cross_month_duplicates, query_in_folder_duplicates,
    query_in_multiple_months, query_only_in_all,
    query_only_in_months, query_total_month_songs, query_untagged,
)
from funcs_check_greek_singles.config import DUPES_DIRNAME, STAGING_DIRNAME  # noqa: E402
from funcs_check_greek_singles.file_actions import (  # noqa: E402
    apply_missing_action, cluster_is_fully_judged, next_group_number, parse_group_range,
    process_inspected, prompt_action_limit, stage_duplicates, unstage_all,
)
from funcs_check_greek_singles.models import (  # noqa: E402
    CrossMonthDupRow, InFolderDupRow, MatchedRow, MultiMonthRow, StagingGroup, UntaggedRow,
)
from funcs_check_greek_singles.normalize import normalize  # noqa: E402
from funcs_check_greek_singles.report import (  # noqa: E402
    render_console, render_staging_groups,
)
from funcs_utils import setup_logging  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-05-26-2209'

SINGLES_ALL_DIRNAME = '01-Singles-All'
SINGLES_BY_MONTH_DIRNAME = '03-Singles-by-Month'
DATA_DIRNAME = 'Data'
LOGS_DIRNAME = 'Logs'
DB_FILENAME = 'songs.sqlite'
DUPES_LOG_FILENAME = 'dupes-deleted-log.csv'
DEFAULT_CONSOLE_WIDTH = 140

logger = logging.getLogger(__name__)


class _UsageError(Exception):
    """Raised on a CLI usage/validation failure; carries the process exit code."""

    def __init__(self, message: str, code: int = 2) -> None:
        """Store the error message and the exit code main() should return."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Dirs:
    """Resolved library directories shared by every action handler."""
    root: Path
    singles_all: Path
    by_month: Path
    staging_dir: Path
    dupes_dir: Path


@dataclass(frozen=True)
class _Scope:
    """Parsed month-range bounds and title-prefix filter for a scan."""
    start_yyyymm: str
    end_yyyymm: str
    range_active: bool
    title_prefix_norm: str


@dataclass(frozen=True)
class _ReportData:
    """The query results selected by --dupes-scope, bundled for rendering."""
    only_in_all: list[MatchedRow]
    only_in_months: list[MatchedRow]
    in_multiple_months: list[MultiMonthRow]
    untagged: list[UntaggedRow]
    in_folder_duplicates: list[InFolderDupRow]
    cross_month_duplicates: list[CrossMonthDupRow]
    total_month_songs: int

    def has_any_rows(self) -> bool:
        """True if any report section produced at least one row."""
        return bool(self.only_in_all or self.only_in_months or self.in_multiple_months
                    or self.untagged or self.in_folder_duplicates or self.cross_month_duplicates)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. argv=None uses sys.argv[1:]."""
    parser = argparse.ArgumentParser(
        description='Cross-check 01-Singles-All vs 03-Singles-by-Month folders.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument(
        '--root', type=Path,
        default=Path.home() / 'Music' / 'Greek',
        help='Greek music root (contains 01-Singles-All and 03-Singles-by-Month). Default: %(default)s',
    )
    parser.add_argument(
        '--title-prefix', type=str, default=None,
        help='Only check songs whose normalized title starts with this Greek prefix '
             '(with or without diacritics; may contain whitespace).',
    )
    parser.add_argument(
        '--start-month', type=str, default=None,
        help="Inclusive lower bound for month folders, format 'yyyy-mm' or 'yyyy' "
             "(the latter expands to <yyyy>-01). When set, the 'only_in_all' section is suppressed.",
    )
    parser.add_argument(
        '--end-month', type=str, default=None,
        help="Inclusive upper bound for month folders, format 'yyyy-mm' or 'yyyy' "
             "(the latter expands to <yyyy>-12). When set, the 'only_in_all' section is suppressed.",
    )
    parser.add_argument(
        '--console-width', type=int, default=None,
        help=f'Console width for Rich tables. Default: detected terminal width, '
             f'or {DEFAULT_CONSOLE_WIDTH} when running under PyCharm/IDE consoles where '
             f'detection fails.',
    )
    parser.add_argument(
        '--missing-action', choices=['copy', 'move'], default=None,
        help="Action for songs missing from 01-Singles-All: 'copy' or 'move' into "
             'per-folder subdirs under All/. Default: %(default)s (report only). '
             'Prompts before acting. Mutually exclusive with --dupes-scope.',
    )
    parser.add_argument(
        '--target-is-year', action='store_true',
        help='When --missing-action is set, group target folders by year only '
             '(All/<YYYY>/) instead of by full month-folder name '
             '(All/<YYYY-MM-...>/). Ignored without --missing-action.',
    )
    parser.add_argument(
        '--dupes-scope', choices=['folder', 'range'], default=None,
        help="Run only a duplicate check (skip cross-folder queries and the "
             "missing-action prompt). 'folder': dupes within each single folder "
             '(01-Singles-All/ when no range, else the in-range month folders). '
             "'range': dupes pooled across all in-range month folders (requires "
             '--start-month/--end-month). Default: %(default)s (full report). '
             'Mutually exclusive with --missing-action.',
    )
    parser.add_argument(
        '--stage-dupes', choices=['dry-run', 'milk-run'], default=None,
        help='Move suspected duplicates (both in-folder and cross-month clusters) into '
             "the staging folder, recording each file's origin in its Grouping tag. "
             "'dry-run' lists intended moves; 'milk-run' performs them. "
             '--start-month/--end-month optionally bound the scan. Mutually exclusive '
             'with --post-inspection, --missing-action, --dupes-scope.',
    )
    parser.add_argument(
        '--post-inspection', choices=['dry-run', 'milk-run'], default=None,
        help='Process inspected files in the staging folder by their Copyright verdict: '
             "'duplicate' -> dupes folder, 'original' -> restored to origin folder. "
             "'dry-run' lists intended actions; 'milk-run' performs them. Mutually "
             'exclusive with --stage-dupes, --missing-action, --dupes-scope.',
    )
    parser.add_argument(
        '--unstage', choices=['dry-run', 'milk-run'], default=None,
        help='Abort a staging run: move every file in the staging folder back to its '
             'origin (from its DUPE-ORIGIN marker), ignoring the verdict and leaving it '
             "untouched. 'dry-run' lists intended moves; 'milk-run' performs them. "
             'Mutually exclusive with the other action flags.',
    )
    parser.add_argument(
        '--staging-dir', type=Path, default=None,
        help=f'Staging folder for suspected duplicates. Default: <root>/{STAGING_DIRNAME}.',
    )
    parser.add_argument(
        '--dupes-dir', type=Path, default=None,
        help=f'Folder for confirmed duplicates (for eventual deletion). Default: <root>/{DUPES_DIRNAME}.',
    )
    parser.add_argument(
        '--staging-groups', type=str, default=None,
        help="Limit --post-inspection / --unstage to a contiguous inclusive range of "
             "staging group folders, given as 'N1,N2' (e.g. 7,10 = grp-0007..grp-0010; "
             '7,7 = grp-0007 only). Default: all group folders.',
    )
    parser.add_argument(
        '--dupes-log', type=Path,
        default=_PROJECT_ROOT / LOGS_DIRNAME / DUPES_LOG_FILENAME,
        help='Persistent CSV log appended on every --post-inspection milk-run that '
             "moves a 'duplicate' to the dupes folder (records its tags incl. the "
             'source URL from the comment tag). Default: %(default)s.',
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable DEBUG-level logging.',
    )
    return parser.parse_args(argv)


def _resolve_console_width(override: int | None) -> int:
    """Pick the console width: CLI override > shutil detection > generous fallback."""
    if override is not None:
        return override
    return shutil.get_terminal_size(fallback=(DEFAULT_CONSOLE_WIDTH, 24)).columns


def _build_staging_groups(*, in_folder_clusters: list[InFolderDupRow],
                          cross_month_clusters: list[CrossMonthDupRow],
                          start_number: int) -> list[StagingGroup]:
    """Build numbered staging groups from the dupe clusters.

    A group is a cross-month cluster (all month copies of a song) or an
    01-Singles-All in-folder cluster; the two never share files. Clusters whose
    members are all already marked 'original' are skipped. Numbering starts at
    start_number.
    """
    candidates: list[InFolderDupRow | CrossMonthDupRow] = []
    candidates.extend(cross_month_clusters)
    candidates.extend(c for c in in_folder_clusters if c.side == SIDE_SINGLES_ALL)
    groups: list[StagingGroup] = []
    number = start_number
    for cluster in candidates:
        if cluster_is_fully_judged(members=cluster.members):
            continue
        groups.append(StagingGroup(number=number, raw_title=cluster.raw_title,
                                   raw_artist=cluster.raw_artist, members=cluster.members))
        number += 1
    return groups


def _validate_action_flags(args: argparse.Namespace) -> None:
    """Raise _UsageError if more than one mutually-exclusive action flag is set."""
    exclusive_actions = [
        ('--dupes-scope', args.dupes_scope is not None),
        ('--missing-action', args.missing_action is not None),
        ('--stage-dupes', args.stage_dupes is not None),
        ('--post-inspection', args.post_inspection is not None),
        ('--unstage', args.unstage is not None),
    ]
    active_actions = [name for name, is_set in exclusive_actions if is_set]
    if len(active_actions) > 1:
        raise _UsageError(f'These options are mutually exclusive: {", ".join(active_actions)}.')


def _resolve_and_check_dirs(args: argparse.Namespace) -> _Dirs:
    """Resolve the root, the two required subdirs, and the staging/dupes dirs.

    Raises _UsageError if root, 01-Singles-All or 03-Singles-by-Month is missing.
    """
    root = args.root.resolve()
    singles_all = root / SINGLES_ALL_DIRNAME
    by_month = root / SINGLES_BY_MONTH_DIRNAME
    if not root.is_dir():
        raise _UsageError(f'Root directory does not exist or is not a directory: {root}')
    if not singles_all.is_dir():
        raise _UsageError(f'Missing required subdirectory: {singles_all}')
    if not by_month.is_dir():
        raise _UsageError(f'Missing required subdirectory: {by_month}')
    return _Dirs(
        root=root, singles_all=singles_all, by_month=by_month,
        staging_dir=(args.staging_dir or (root / STAGING_DIRNAME)).resolve(),
        dupes_dir=(args.dupes_dir or (root / DUPES_DIRNAME)).resolve(),
    )


def _parse_group_range_arg(args: argparse.Namespace) -> tuple[int, int] | None:
    """Parse --staging-groups into an inclusive (lo, hi) range, or None if unset.

    Raises _UsageError on malformed input.
    """
    if not args.staging_groups:
        return None
    try:
        return parse_group_range(value=args.staging_groups)
    except ValueError as exc:
        raise _UsageError(str(exc)) from exc


def _parse_month_bounds(args: argparse.Namespace) -> tuple[str, str]:
    """Parse --start-month/--end-month into (start_yyyymm, end_yyyymm). Raises _UsageError."""
    try:
        start_yyyymm = parse_month_arg(value=args.start_month, is_end=False) if args.start_month else ''
        end_yyyymm = parse_month_arg(value=args.end_month, is_end=True) if args.end_month else ''
    except ValueError as exc:
        raise _UsageError(str(exc)) from exc
    return start_yyyymm, end_yyyymm


def _resolved_scope(args: argparse.Namespace) -> _Scope:
    """Parse the month range and title-prefix filter into a _Scope (no logging).

    Raises _UsageError on a malformed month, start > end, or --dupes-scope range
    given without any month bound.
    """
    start_yyyymm, end_yyyymm = _parse_month_bounds(args=args)
    if start_yyyymm and end_yyyymm and start_yyyymm > end_yyyymm:
        raise _UsageError(f'--start-month ({start_yyyymm}) is later than --end-month ({end_yyyymm}).')
    if args.dupes_scope == 'range' and not (start_yyyymm or end_yyyymm):
        raise _UsageError('--dupes-scope range requires --start-month and/or --end-month.')
    return _Scope(
        start_yyyymm=start_yyyymm, end_yyyymm=end_yyyymm,
        range_active=bool(start_yyyymm or end_yyyymm),
        title_prefix_norm=normalize(text=args.title_prefix) if args.title_prefix else '',
    )


def _log_scan_scope(args: argparse.Namespace, scope: _Scope) -> None:
    """Emit the informational range / dupes-scope / title-prefix lines (no behavior change)."""
    start_label = scope.start_yyyymm or '-inf'
    end_label = scope.end_yyyymm or '+inf'
    if scope.range_active and args.dupes_scope is None:
        logger.info(f'Month range is active: {start_label}..{end_label}; '
                    f"the 'only_in_all' section will be suppressed.")
    if args.dupes_scope == 'folder':
        folder_scope = (f'in-range month folders ({start_label}..{end_label})'
                        if scope.range_active else SINGLES_ALL_DIRNAME)
        logger.info(f'Dupes-scope=folder: scanning {folder_scope}; cross-folder checks skipped.')
    elif args.dupes_scope == 'range':
        logger.info(f'Dupes-scope=range: pooling in-range month folders '
                    f'({start_label}..{end_label}); cross-folder checks skipped.')
    if scope.title_prefix_norm:
        logger.info(f'Title-prefix filter: {args.title_prefix!r} (normalized: {scope.title_prefix_norm!r})')


def _ensure_data_dir() -> Path:
    """Create (if needed) and return the Data directory under the project root."""
    data_dir = _PROJECT_ROOT / DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _run_post_inspection(*, args: argparse.Namespace, dirs: _Dirs,
                         group_range: tuple[int, int] | None) -> int:
    """Process inspected staging files by their Copyright verdict (--post-inspection)."""
    if not dirs.staging_dir.is_dir():
        raise _UsageError(f'Staging folder does not exist: {dirs.staging_dir}')
    post_dry_run = args.post_inspection == 'dry-run'
    dupes_log = args.dupes_log.resolve()
    dupes_log.parent.mkdir(parents=True, exist_ok=True)
    scope_label = f' (groups {group_range[0]}-{group_range[1]})' if group_range else ''
    logger.info(f'Post-inspection ({args.post_inspection}) scanning {dirs.staging_dir}{scope_label}...')
    inspect_summary = process_inspected(
        staging_dir=dirs.staging_dir, root=dirs.root, dupes_dir=dirs.dupes_dir,
        group_range=group_range, dry_run=post_dry_run, dupes_log=dupes_log)
    print(
        f'\nPost-inspection {args.post_inspection} complete: '
        f'{inspect_summary.moved_to_dupes} -> {dirs.dupes_dir.name}/, '
        f'{inspect_summary.restored} restored, {inspect_summary.pending} pending, '
        f'{inspect_summary.ambiguous} ambiguous, {inspect_summary.no_marker} unmarked, '
        f'{inspect_summary.failed} failed'
    )
    return 0


def _run_unstage(*, args: argparse.Namespace, dirs: _Dirs,
                 group_range: tuple[int, int] | None) -> int:
    """Move every staged file back to its origin, ignoring verdicts (--unstage)."""
    if not dirs.staging_dir.is_dir():
        raise _UsageError(f'Staging folder does not exist: {dirs.staging_dir}')
    unstage_dry_run = args.unstage == 'dry-run'
    scope_label = f' (groups {group_range[0]}-{group_range[1]})' if group_range else ''
    logger.info(f'Unstage ({args.unstage}) scanning {dirs.staging_dir}{scope_label}...')
    unstage_summary = unstage_all(staging_dir=dirs.staging_dir, root=dirs.root,
                                  group_range=group_range, dry_run=unstage_dry_run)
    print(f'\nUnstage {args.unstage} complete: {unstage_summary.restored} restored, '
          f'{unstage_summary.no_marker} unmarked, {unstage_summary.failed} failed')
    return 0


def _scan_into_db(*, conn: sqlite3.Connection, dirs: _Dirs, scope: _Scope,
                  scan_singles_all: bool, scan_months: bool) -> int:
    """Scan the requested sides into the DB and return the month-folder count.

    Logs one 'Scanning <folder>...' line per folder scanned. Does not commit.
    """
    if scan_singles_all:
        logger.info(f'Scanning {dirs.singles_all}...')
        for song in collect_songs(directory=dirs.singles_all,
                                  title_prefix_norm=scope.title_prefix_norm, progress_every=200):
            insert_song(conn=conn, song=song, side=SIDE_SINGLES_ALL, month_folder=None)
    month_count = 0
    if scan_months:
        for month_dir in iter_month_folders(by_month_root=dirs.by_month,
                                            start_yyyymm=scope.start_yyyymm,
                                            end_yyyymm=scope.end_yyyymm):
            logger.info(f'Scanning {month_dir.name}...')
            for song in collect_songs(directory=month_dir, title_prefix_norm=scope.title_prefix_norm):
                insert_song(conn=conn, song=song, side=SIDE_MONTH, month_folder=month_dir.name)
            month_count += 1
    return month_count


def _run_stage(*, args: argparse.Namespace, dirs: _Dirs, conn: sqlite3.Connection,
               scope: _Scope) -> int:
    """Stage suspected duplicate groups into the staging folder (--stage-dupes).

    With a month range, focus on the in-range month folders only (matching
    --dupes-scope semantics). Without a range, also scan 01-Singles-All so in-folder
    duplicates within the master collection are caught too.
    """
    if scope.range_active:
        logger.info(f'Staging scope: in-range month folders only '
                    f"({scope.start_yyyymm or '-inf'}..{scope.end_yyyymm or '+inf'}); "
                    f'01-Singles-All is not scanned.')
    else:
        logger.info('Staging scope: 01-Singles-All + all month folders.')
    _scan_into_db(conn=conn, dirs=dirs, scope=scope,
                  scan_singles_all=not scope.range_active, scan_months=True)
    conn.commit()
    # Build one group per song: cross-month clusters (all month copies) +
    # 01-Singles-All in-folder clusters. Groups all-marked 'original' are skipped
    # (cluster_is_fully_judged inside _build_staging_groups); numbers continue past
    # any leftover grp-NNNN folders so a re-stage appends.
    groups = _build_staging_groups(
        in_folder_clusters=query_in_folder_duplicates(conn=conn),
        cross_month_clusters=query_cross_month_duplicates(conn=conn),
        start_number=next_group_number(staging_dir=dirs.staging_dir),
    )
    if not groups:
        logger.info('No new suspected duplicates to stage.')
        return 0
    console = Console(width=_resolve_console_width(override=args.console_width))
    render_staging_groups(console=console, groups=groups)
    stage_dry_run = args.stage_dupes == 'dry-run'
    file_total = sum(len(group.members) for group in groups)
    logger.info(f'Staging {len(groups)} group(s) / {file_total} file(s) '
                f'({args.stage_dupes}) into {dirs.staging_dir}...')
    stage_summary = stage_duplicates(
        groups=groups, root=dirs.root, staging_dir=dirs.staging_dir, dry_run=stage_dry_run)
    print(f'\nStaging {args.stage_dupes} complete: {stage_summary.staged} staged '
          f'in {len(groups)} group(s), {stage_summary.skipped} skipped, '
          f'{stage_summary.failed} failed (of {stage_summary.attempted} attempted)')
    return 0


def _query_report(*, conn: sqlite3.Connection, dupes_scope: str | None,
                  range_active: bool) -> _ReportData:
    """Run the queries selected by --dupes-scope and bundle them into _ReportData."""
    only_in_all: list[MatchedRow] = []
    only_in_months: list[MatchedRow] = []
    in_multiple_months: list[MultiMonthRow] = []
    untagged: list[UntaggedRow] = []
    in_folder_duplicates: list[InFolderDupRow] = []
    cross_month_duplicates: list[CrossMonthDupRow] = []
    total_month_songs = 0
    if dupes_scope == 'folder':
        in_folder_duplicates = query_in_folder_duplicates(conn=conn)
    elif dupes_scope == 'range':
        cross_month_duplicates = query_cross_month_duplicates(conn=conn)
    else:
        only_in_all = [] if range_active else query_only_in_all(conn=conn)
        only_in_months = query_only_in_months(conn=conn)
        in_multiple_months = query_in_multiple_months(conn=conn)
        untagged = query_untagged(conn=conn)
        in_folder_duplicates = query_in_folder_duplicates(conn=conn)
        total_month_songs = query_total_month_songs(conn=conn)
    return _ReportData(
        only_in_all=only_in_all, only_in_months=only_in_months,
        in_multiple_months=in_multiple_months, untagged=untagged,
        in_folder_duplicates=in_folder_duplicates,
        cross_month_duplicates=cross_month_duplicates, total_month_songs=total_month_songs)


def _run_missing_action(*, args: argparse.Namespace, singles_all: Path,
                        console: Console, only_in_months: list[MatchedRow]) -> None:
    """Prompt for and apply the optional copy/move of songs missing from 01-Singles-All."""
    if not only_in_months:
        logger.info('No songs missing from 01-Singles-All -- nothing to copy/move.')
        return
    total_bytes = sum(row.size_bytes for row in only_in_months)
    limit = prompt_action_limit(
        action=args.missing_action, row_count=len(only_in_months),
        total_bytes=total_bytes, target_is_year=args.target_is_year)
    if limit is None:
        logger.info('Action cancelled by user.')
        return
    summary = apply_missing_action(
        rows=only_in_months, singles_all_root=singles_all,
        action=args.missing_action, target_is_year=args.target_is_year, limit=limit)
    console.print(
        f'\n[bold]{args.missing_action.capitalize()} complete '
        f'(processed {summary.attempted} of {len(only_in_months)}):[/bold] '
        f'{summary.succeeded} succeeded, {summary.failed} failed, '
        f'{summary.skipped} skipped'
    )


def _run_report(*, args: argparse.Namespace, dirs: _Dirs, conn: sqlite3.Connection,
                scope: _Scope, db_path: Path) -> int:
    """Run the cross-check report and the optional --missing-action (default path)."""
    # 'folder' (no range) checks 01-Singles-All only; 'range' is months only.
    scan_singles_all = (args.dupes_scope != 'range'
                        and not (args.dupes_scope == 'folder' and scope.range_active))
    scan_months = args.dupes_scope != 'folder' or scope.range_active
    month_count = _scan_into_db(conn=conn, dirs=dirs, scope=scope,
                                scan_singles_all=scan_singles_all, scan_months=scan_months)
    if scan_months:
        logger.info(f'Scanned {month_count} month folder(s).')
        if scope.range_active and month_count == 0:
            logger.info('Month range is active but no month folders fell within the range.')
    conn.commit()

    data = _query_report(conn=conn, dupes_scope=args.dupes_scope, range_active=scope.range_active)
    if scope.title_prefix_norm and not data.has_any_rows():
        logger.info('No songs matched the title prefix on either side.')

    console = Console(width=_resolve_console_width(override=args.console_width))
    render_console(
        console=console,
        only_in_all=data.only_in_all,
        only_in_months=data.only_in_months,
        in_multiple_months=data.in_multiple_months,
        untagged=data.untagged,
        in_folder_duplicates=data.in_folder_duplicates,
        cross_month_duplicates=data.cross_month_duplicates,
        title_prefix=args.title_prefix,
        total_month_songs=data.total_month_songs,
        range_active=scope.range_active,
        start_yyyymm=scope.start_yyyymm,
        end_yyyymm=scope.end_yyyymm,
        dupes_scope=args.dupes_scope,
    )
    console.print(f'\n[bold]Snapshot:[/bold] {db_path}')

    if args.missing_action is not None:
        _run_missing_action(args=args, singles_all=dirs.singles_all,
                            console=console, only_in_months=data.only_in_months)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point. Parse args, then validate and dispatch to the selected action."""
    args = parse_args(argv=argv)
    setup_logging(verbose=args.verbose, log_to_file=True, log_dir=_PROJECT_ROOT / LOGS_DIRNAME)
    try:
        _validate_action_flags(args=args)
        dirs = _resolve_and_check_dirs(args=args)
        group_range = _parse_group_range_arg(args=args)
        if args.post_inspection is not None:
            return _run_post_inspection(args=args, dirs=dirs, group_range=group_range)
        if args.unstage is not None:
            return _run_unstage(args=args, dirs=dirs, group_range=group_range)
        scope = _resolved_scope(args=args)
        _log_scan_scope(args=args, scope=scope)
        db_path = _ensure_data_dir() / DB_FILENAME
        conn = init_db(db_path=db_path)
        try:
            if args.stage_dupes is not None:
                return _run_stage(args=args, dirs=dirs, conn=conn, scope=scope)
            return _run_report(args=args, dirs=dirs, conn=conn, scope=scope, db_path=db_path)
        finally:
            conn.close()
    except _UsageError as exc:
        logger.error(str(exc))
        return exc.code


if __name__ == '__main__':
    sys.exit(main())
