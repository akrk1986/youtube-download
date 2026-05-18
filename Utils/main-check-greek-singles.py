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
    query_in_multiple_months, query_only_in_all,
    query_only_in_months, query_total_month_songs, query_untagged,
)
from funcs_check_greek_singles.models import MatchedRow  # noqa: E402
from funcs_check_greek_singles.normalize import normalize  # noqa: E402
from funcs_check_greek_singles.report import render_console, write_csv  # noqa: E402
from funcs_utils import setup_logging  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-05-18-1933'

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
        '--verbose', action='store_true',
        help='Enable DEBUG-level logging.',
    )
    return parser.parse_args(argv)


def _resolve_console_width(override: int | None) -> int:
    """Pick the console width: CLI override > shutil detection > generous fallback."""
    if override is not None:
        return override
    return shutil.get_terminal_size(fallback=(DEFAULT_CONSOLE_WIDTH, 24)).columns


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = parse_args(argv=argv)
    setup_logging(verbose=args.verbose, log_to_file=True, log_dir=_PROJECT_ROOT / LOGS_DIRNAME)

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
    if range_active:
        logger.info(
            f"Month range is active: {start_yyyymm or '-inf'}..{end_yyyymm or '+inf'}; "
            f"the 'only_in_all' section will be suppressed."
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
        logger.info(f'Scanning {singles_all}...')
        for song in collect_songs(directory=singles_all, title_prefix_norm=title_prefix_norm,
                                  progress_every=200):
            insert_song(conn=conn, song=song, side=SIDE_SINGLES_ALL, month_folder=None)

        month_count = 0
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

        only_in_all: list[MatchedRow] = [] if range_active else query_only_in_all(conn=conn)
        only_in_months = query_only_in_months(conn=conn)
        in_multiple_months = query_in_multiple_months(conn=conn)
        untagged = query_untagged(conn=conn)
        total_month_songs = query_total_month_songs(conn=conn)

        if title_prefix_norm and not (only_in_all or only_in_months or in_multiple_months or untagged):
            logger.info('No songs matched the title prefix on either side.')

        console = Console(width=_resolve_console_width(override=args.console_width))
        render_console(
            console=console,
            only_in_all=only_in_all,
            only_in_months=only_in_months,
            in_multiple_months=in_multiple_months,
            untagged=untagged,
            title_prefix=args.title_prefix,
            total_month_songs=total_month_songs,
            range_active=range_active,
            start_yyyymm=start_yyyymm,
            end_yyyymm=end_yyyymm,
        )

        timestamp = arrow.now().format('YYYY-MM-DD-HHmm')
        csv_path = args.csv_dir / f'greek-singles-check-{timestamp}.csv'
        write_csv(
            csv_path=csv_path,
            only_in_all=only_in_all,
            only_in_months=only_in_months,
            in_multiple_months=in_multiple_months,
            untagged=untagged,
        )
        console.print(f'\n[bold]CSV written:[/bold] {csv_path}')
        console.print(f'[bold]Snapshot:[/bold] {db_path}')
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
