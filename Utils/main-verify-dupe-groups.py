#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
Verify the dupe-group staging folders after a staging run: each
``Staging-Dupes/grp-NNNN/`` folder should hold exactly one song (all files
sharing one normalized title+artist). Reports any folder that does not -- most
importantly a folder holding two different songs (e.g. files moved into the wrong
group after the run). Implementation lives in
``funcs_check_greek_singles/verify_groups.py``.

Run with --help for usage; --version for the build timestamp.
"""
import argparse
import logging
import shutil
import sys
from pathlib import Path

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from funcs_check_greek_singles.config import STAGING_DIRNAME  # noqa: E402
from funcs_check_greek_singles.verify_groups import (  # noqa: E402
    STATUS_EMPTY, STATUS_MISGROUPED, STATUS_OK, STATUS_SINGLETON, STATUS_UNTAGGED,
    GroupReport, verify_staging_dir,
)
from funcs_utils import setup_logging  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-05-25-1941'

SINGLES_ROOT_DEFAULT = Path.home() / 'Music' / 'Greek'
DEFAULT_CONSOLE_WIDTH = 140

# Rich style + one-word label per status, for the report table.
_STATUS_STYLE = {
    STATUS_OK: 'green',
    STATUS_MISGROUPED: 'bold red',
    STATUS_UNTAGGED: 'yellow',
    STATUS_SINGLETON: 'bold red',
    STATUS_EMPTY: 'bold red',
}

# Statuses that make a group invalid after a clean staging run (-> hard FAIL).
# untagged stays a softer CHECK -- the file just can't be verified, not mis-staged.
_FAIL_STATUSES = (STATUS_MISGROUPED, STATUS_SINGLETON, STATUS_EMPTY)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. argv=None uses sys.argv[1:]."""
    parser = argparse.ArgumentParser(
        description='Verify that each Staging-Dupes/grp-NNNN folder holds exactly one song.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument(
        '--root', type=Path, default=SINGLES_ROOT_DEFAULT,
        help='Greek music root (contains the staging folder). Default: %(default)s',
    )
    parser.add_argument(
        '--staging-dir', type=Path, default=None,
        help=f'Folder holding the grp-NNNN subfolders to verify. Default: <root>/{STAGING_DIRNAME}.',
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable DEBUG-level logging.',
    )
    return parser.parse_args(argv)


def _distinct_song_labels(report: GroupReport) -> list[str]:
    """Return one 'raw title / raw artist' label per distinct song, in key order."""
    by_key: dict[object, str] = {}
    for song in report.songs:
        if song.key is not None and song.key not in by_key:
            by_key[song.key] = f'{song.raw_title} / {song.raw_artist}'
    ordered_keys = list(report.distinct_keys)
    return [by_key[key] for key in ordered_keys if key in by_key]


def _untagged_names(report: GroupReport) -> list[str]:
    """Return the file names in the group that are missing a title/artist key."""
    return [Path(song.file_path).name for song in report.songs if song.key is None]


def _detail(report: GroupReport) -> str:
    """One-line, human-readable description of a group's contents for the table."""
    if report.status == STATUS_EMPTY:
        return '(no audio files)'
    if report.status == STATUS_MISGROUPED:
        labels = _distinct_song_labels(report=report)
        return f'{len(labels)} different songs: ' + ' | '.join(labels)
    if report.status == STATUS_UNTAGGED:
        missing = _untagged_names(report=report)
        return 'missing title/artist: ' + ', '.join(missing)
    labels = _distinct_song_labels(report=report)
    return labels[0] if labels else ''


def render_reports(console: Console, reports: list[GroupReport]) -> None:
    """Print a per-group status table followed by a summary line."""
    table = Table(title=f'Dupe-group verification ({len(reports)} group folder(s))',
                  title_justify='left', header_style='bold cyan', expand=True)
    table.add_column('Group', no_wrap=True)
    table.add_column('Files', justify='right', width=5)
    table.add_column('Status', no_wrap=True)
    table.add_column('Contents', overflow='fold', ratio=1)
    for report in reports:
        style = _STATUS_STYLE.get(report.status, '')
        table.add_row(
            report.name,
            str(len(report.songs)),
            f'[{style}]{report.status}[/{style}]' if style else report.status,
            _detail(report=report),
        )
    console.print(table)

    counts: dict[str, int] = {}
    for report in reports:
        counts[report.status] = counts.get(report.status, 0) + 1
    summary = ' | '.join(f'{status}: {counts[status]}' for status in sorted(counts))
    console.print(f'\n[bold]Summary:[/bold] {summary}')
    fail_count = sum(counts.get(status, 0) for status in _FAIL_STATUSES)
    if all(report.is_ok for report in reports):
        console.print('[bold green]PASS[/bold green] -- every group holds exactly one song.')
    elif fail_count:
        console.print(f'[bold red]FAIL[/bold red] -- {fail_count} group(s) are not a valid dupe '
                      'group (misgrouped / singleton / empty).')
    else:
        console.print('[bold yellow]CHECK[/bold yellow] -- some groups need attention (untagged).')


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code (0 ok, 1 issues, 2 usage error)."""
    args = parse_args(argv=argv)
    setup_logging(verbose=args.verbose, log_to_file=True, log_dir=_PROJECT_ROOT / 'Logs')

    staging_dir = (args.staging_dir or (args.root.resolve() / STAGING_DIRNAME)).resolve()
    if not staging_dir.is_dir():
        logger.error(f'Staging folder does not exist or is not a directory: {staging_dir}')
        return 2

    logger.info(f'Verifying dupe groups under {staging_dir}...')
    reports = verify_staging_dir(staging_dir=staging_dir)

    console = Console(width=shutil.get_terminal_size(
        fallback=(DEFAULT_CONSOLE_WIDTH, 24)).columns)
    if not reports:
        console.print(f'No grp-NNNN folders found under {staging_dir}.')
        return 0

    render_reports(console=console, reports=reports)
    return 0 if all(report.is_ok for report in reports) else 1


if __name__ == '__main__':
    sys.exit(main())
