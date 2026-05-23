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
import sys
from pathlib import Path

import arrow

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
    archive_previous_db, init_db, insert_song,
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
    CrossMonthDupRow, InFolderDupRow, MatchedRow, StagingGroup,
)
from funcs_check_greek_singles.normalize import normalize  # noqa: E402
from funcs_check_greek_singles.report import (  # noqa: E402
    render_console, render_staging_groups, write_csv,
)
from funcs_utils import setup_logging  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-05-20-2103'

SINGLES_ALL_DIRNAME = '01-Singles-All'
SINGLES_BY_MONTH_DIRNAME = '03-Singles-by-Month'
DATA_DIRNAME = 'Data'
LOGS_DIRNAME = 'Logs'
DB_FILENAME = 'songs.sqlite'
DEFAULT_CONSOLE_WIDTH = 140

logger = logging.getLogger(__name__)


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
        '--csv-dir', type=Path,
        default=_PROJECT_ROOT / LOGS_DIRNAME,
        help='Directory for the timestamped CSV report. Default: %(default)s',
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


def main(argv: list[str] | None = None) -> int:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-return-statements
    """Entry point. Returns the process exit code."""
    args = parse_args(argv=argv)
    setup_logging(verbose=args.verbose, log_to_file=True, log_dir=_PROJECT_ROOT / LOGS_DIRNAME)

    exclusive_actions = [
        ('--dupes-scope', args.dupes_scope is not None),
        ('--missing-action', args.missing_action is not None),
        ('--stage-dupes', args.stage_dupes is not None),
        ('--post-inspection', args.post_inspection is not None),
        ('--unstage', args.unstage is not None),
    ]
    active_actions = [name for name, is_set in exclusive_actions if is_set]
    if len(active_actions) > 1:
        logger.error(f'These options are mutually exclusive: {", ".join(active_actions)}.')
        return 2

    root = args.root.resolve()
    singles_all = root / SINGLES_ALL_DIRNAME
    by_month = root / SINGLES_BY_MONTH_DIRNAME

    if not root.is_dir():
        logger.error(f'Root directory does not exist or is not a directory: {root}')
        return 2
    if not singles_all.is_dir():
        logger.error(f'Missing required subdirectory: {singles_all}')
        return 2
    if not by_month.is_dir():
        logger.error(f'Missing required subdirectory: {by_month}')
        return 2

    staging_dir = (args.staging_dir or (root / STAGING_DIRNAME)).resolve()
    dupes_dir = (args.dupes_dir or (root / DUPES_DIRNAME)).resolve()

    try:
        group_range = parse_group_range(value=args.staging_groups) if args.staging_groups else None
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    if args.post_inspection is not None:
        if not staging_dir.is_dir():
            logger.error(f'Staging folder does not exist: {staging_dir}')
            return 2
        post_dry_run = args.post_inspection == 'dry-run'
        scope = f' (groups {group_range[0]}-{group_range[1]})' if group_range else ''
        logger.info(f'Post-inspection ({args.post_inspection}) scanning {staging_dir}{scope}...')
        inspect_summary = process_inspected(
            staging_dir=staging_dir, root=root, dupes_dir=dupes_dir,
            group_range=group_range, dry_run=post_dry_run)
        print(
            f'\nPost-inspection {args.post_inspection} complete: '
            f'{inspect_summary.moved_to_dupes} -> {dupes_dir.name}/, '
            f'{inspect_summary.restored} restored, {inspect_summary.pending} pending, '
            f'{inspect_summary.ambiguous} ambiguous, {inspect_summary.no_marker} unmarked, '
            f'{inspect_summary.failed} failed'
        )
        return 0

    if args.unstage is not None:
        if not staging_dir.is_dir():
            logger.error(f'Staging folder does not exist: {staging_dir}')
            return 2
        unstage_dry_run = args.unstage == 'dry-run'
        scope = f' (groups {group_range[0]}-{group_range[1]})' if group_range else ''
        logger.info(f'Unstage ({args.unstage}) scanning {staging_dir}{scope}...')
        unstage_summary = unstage_all(staging_dir=staging_dir, root=root,
                                      group_range=group_range, dry_run=unstage_dry_run)
        print(f'\nUnstage {args.unstage} complete: {unstage_summary.restored} restored, '
              f'{unstage_summary.no_marker} unmarked, {unstage_summary.failed} failed')
        return 0

    try:
        start_yyyymm = parse_month_arg(value=args.start_month, is_end=False) if args.start_month else ''
        end_yyyymm = parse_month_arg(value=args.end_month, is_end=True) if args.end_month else ''
    except ValueError as exc:
        logger.error(str(exc))
        return 2
    if start_yyyymm and end_yyyymm and start_yyyymm > end_yyyymm:
        logger.error(f'--start-month ({start_yyyymm}) is later than --end-month ({end_yyyymm}).')
        return 2
    range_active = bool(start_yyyymm or end_yyyymm)
    if args.dupes_scope == 'range' and not range_active:
        logger.error('--dupes-scope range requires --start-month and/or --end-month.')
        return 2
    if range_active and args.dupes_scope is None:
        logger.info(
            f"Month range is active: {start_yyyymm or '-inf'}..{end_yyyymm or '+inf'}; "
            f"the 'only_in_all' section will be suppressed."
        )
    if args.dupes_scope == 'folder':
        scope = (f'in-range month folders ({start_yyyymm or "-inf"}..{end_yyyymm or "+inf"})'
                 if range_active else SINGLES_ALL_DIRNAME)
        logger.info(f'Dupes-scope=folder: scanning {scope}; cross-folder checks skipped.')
    elif args.dupes_scope == 'range':
        logger.info(
            f'Dupes-scope=range: pooling in-range month folders '
            f"({start_yyyymm or '-inf'}..{end_yyyymm or '+inf'}); cross-folder checks skipped."
        )

    data_dir = _PROJECT_ROOT / DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / DB_FILENAME
    archive_previous_db(db_path=db_path)

    args.csv_dir.mkdir(parents=True, exist_ok=True)

    title_prefix_norm = normalize(text=args.title_prefix) if args.title_prefix else ''
    if title_prefix_norm:
        logger.info(f'Title-prefix filter: {args.title_prefix!r} (normalized: {title_prefix_norm!r})')

    conn = init_db(db_path=db_path)
    try:
        if args.stage_dupes is not None:
            # With a month range, focus on the in-range month folders only (matching
            # --dupes-scope semantics). Without a range, also scan 01-Singles-All so
            # in-folder duplicates within the master collection are caught too.
            if range_active:
                logger.info(f'Staging scope: in-range month folders only '
                            f"({start_yyyymm or '-inf'}..{end_yyyymm or '+inf'}); "
                            f'01-Singles-All is not scanned.')
            else:
                logger.info('Staging scope: 01-Singles-All + all month folders.')
                logger.info(f'Scanning {singles_all}...')
                for song in collect_songs(directory=singles_all, title_prefix_norm=title_prefix_norm,
                                          progress_every=200):
                    insert_song(conn=conn, song=song, side=SIDE_SINGLES_ALL, month_folder=None)
            for month_dir in iter_month_folders(
                    by_month_root=by_month, start_yyyymm=start_yyyymm, end_yyyymm=end_yyyymm):
                logger.info(f'Scanning {month_dir.name}...')
                for song in collect_songs(directory=month_dir, title_prefix_norm=title_prefix_norm):
                    insert_song(conn=conn, song=song, side=SIDE_MONTH, month_folder=month_dir.name)
            conn.commit()
            # Build one group per song: cross-month clusters (all month copies) +
            # 01-Singles-All in-folder clusters. Groups all-marked 'original' are
            # skipped (cluster_is_fully_judged inside _build_staging_groups); numbers
            # continue past any leftover grp-NNNN folders so a re-stage appends.
            groups = _build_staging_groups(
                in_folder_clusters=query_in_folder_duplicates(conn=conn),
                cross_month_clusters=query_cross_month_duplicates(conn=conn),
                start_number=next_group_number(staging_dir=staging_dir),
            )
            if not groups:
                logger.info('No new suspected duplicates to stage.')
                return 0
            console = Console(width=_resolve_console_width(override=args.console_width))
            render_staging_groups(console=console, groups=groups)
            stage_dry_run = args.stage_dupes == 'dry-run'
            file_total = sum(len(group.members) for group in groups)
            logger.info(f'Staging {len(groups)} group(s) / {file_total} file(s) '
                        f'({args.stage_dupes}) into {staging_dir}...')
            stage_summary = stage_duplicates(
                groups=groups, root=root, staging_dir=staging_dir, dry_run=stage_dry_run)
            print(f'\nStaging {args.stage_dupes} complete: {stage_summary.staged} staged '
                  f'in {len(groups)} group(s), {stage_summary.skipped} skipped, '
                  f'{stage_summary.failed} failed (of {stage_summary.attempted} attempted)')
            return 0

        # 'folder' (no range) checks 01-Singles-All only; 'range' is months only.
        scan_singles_all = args.dupes_scope != 'range' and not (args.dupes_scope == 'folder'
                                                                and range_active)
        scan_months = args.dupes_scope != 'folder' or range_active

        if scan_singles_all:
            logger.info(f'Scanning {singles_all}...')
            for song in collect_songs(directory=singles_all, title_prefix_norm=title_prefix_norm,
                                      progress_every=200):
                insert_song(conn=conn, song=song, side=SIDE_SINGLES_ALL, month_folder=None)

        month_count = 0
        if scan_months:
            for month_dir in iter_month_folders(
                    by_month_root=by_month, start_yyyymm=start_yyyymm, end_yyyymm=end_yyyymm):
                logger.info(f'Scanning {month_dir.name}...')
                for song in collect_songs(directory=month_dir, title_prefix_norm=title_prefix_norm):
                    insert_song(conn=conn, song=song, side=SIDE_MONTH, month_folder=month_dir.name)
                month_count += 1
            logger.info(f'Scanned {month_count} month folder(s).')
            if range_active and month_count == 0:
                logger.info('Month range is active but no month folders fell within the range.')
        conn.commit()

        only_in_all: list[MatchedRow] = []
        only_in_months: list[MatchedRow] = []
        in_multiple_months = []  # type: ignore[var-annotated]
        untagged = []  # type: ignore[var-annotated]
        in_folder_duplicates = []  # type: ignore[var-annotated]
        cross_month_duplicates = []  # type: ignore[var-annotated]
        total_month_songs = 0
        if args.dupes_scope == 'folder':
            in_folder_duplicates = query_in_folder_duplicates(conn=conn)
        elif args.dupes_scope == 'range':
            cross_month_duplicates = query_cross_month_duplicates(conn=conn)
        else:
            only_in_all = [] if range_active else query_only_in_all(conn=conn)
            only_in_months = query_only_in_months(conn=conn)
            in_multiple_months = query_in_multiple_months(conn=conn)
            untagged = query_untagged(conn=conn)
            in_folder_duplicates = query_in_folder_duplicates(conn=conn)
            total_month_songs = query_total_month_songs(conn=conn)

        if title_prefix_norm and not (only_in_all or only_in_months
                                      or in_multiple_months or untagged
                                      or in_folder_duplicates or cross_month_duplicates):
            logger.info('No songs matched the title prefix on either side.')

        console = Console(width=_resolve_console_width(override=args.console_width))
        render_console(
            console=console,
            only_in_all=only_in_all,
            only_in_months=only_in_months,
            in_multiple_months=in_multiple_months,
            untagged=untagged,
            in_folder_duplicates=in_folder_duplicates,
            cross_month_duplicates=cross_month_duplicates,
            title_prefix=args.title_prefix,
            total_month_songs=total_month_songs,
            range_active=range_active,
            start_yyyymm=start_yyyymm,
            end_yyyymm=end_yyyymm,
            dupes_scope=args.dupes_scope,
        )

        timestamp = arrow.now().format('YYYY-MM-DD-HHmm')
        csv_path = args.csv_dir / f'greek-singles-check-{timestamp}.csv'
        write_csv(
            csv_path=csv_path,
            only_in_all=only_in_all,
            only_in_months=only_in_months,
            in_multiple_months=in_multiple_months,
            untagged=untagged,
            in_folder_duplicates=in_folder_duplicates,
            cross_month_duplicates=cross_month_duplicates,
        )
        console.print(f'\n[bold]CSV written:[/bold] {csv_path}')
        console.print(f'[bold]Snapshot:[/bold] {db_path}')

        if args.missing_action is not None:
            if not only_in_months:
                logger.info('No songs missing from 01-Singles-All -- nothing to copy/move.')
            else:
                total_bytes = sum(row.size_bytes for row in only_in_months)
                limit = prompt_action_limit(
                    action=args.missing_action,
                    row_count=len(only_in_months),
                    total_bytes=total_bytes,
                    target_is_year=args.target_is_year,
                )
                if limit is None:
                    logger.info('Action cancelled by user.')
                else:
                    summary = apply_missing_action(
                        rows=only_in_months,
                        singles_all_root=singles_all,
                        action=args.missing_action,
                        target_is_year=args.target_is_year,
                        limit=limit,
                    )
                    console.print(
                        f'\n[bold]{args.missing_action.capitalize()} complete '
                        f'(processed {summary.attempted} of {len(only_in_months)}):[/bold] '
                        f'{summary.succeeded} succeeded, {summary.failed} failed, '
                        f'{summary.skipped} skipped'
                    )
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
