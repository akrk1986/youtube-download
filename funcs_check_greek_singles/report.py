"""Console (Rich) + CSV report rendering for the cross-checker."""
import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from funcs_check_greek_singles.models import MatchedRow, MultiMonthRow, UntaggedRow
from funcs_check_greek_singles.normalize import format_duration, missing_tag_fields

_SERIAL_WIDTH = 4
_MB = 1024 * 1024
_GB = _MB * 1024


def _format_size(size_bytes: int) -> str:
    """Render a byte count as '<X.XX> MB' (under 1 GB) or '<X.XX> GB'."""
    if size_bytes <= 0:
        return '0 MB'
    if size_bytes < _GB:
        return f'{size_bytes / _MB:.2f} MB'
    return f'{size_bytes / _GB:.2f} GB'


def _format_folders(folders: str | None) -> str:
    if not folders:
        return ''
    return '; '.join(part.strip() for part in folders.split(','))


def _display_path(file_path: str, month_folder: str | None) -> str:
    """Render a friendly file label: 'All/<name>' for singles-all, '<month>/<name>' for months."""
    name = Path(file_path).name
    if month_folder:
        return f'{month_folder}/{name}'
    return f'All/{name}'


def _add_matched_table(console: Console, title: str, rows: list[MatchedRow]) -> None:
    table = Table(title=title, title_justify='left', show_lines=False,
                  header_style='bold cyan', expand=True)
    table.add_column('#', justify='right', width=_SERIAL_WIDTH, style='dim')
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Year', justify='right')
    table.add_column('Duration', justify='right')
    table.add_column('File', overflow='fold', ratio=3)
    for idx, row in enumerate(rows, start=1):
        table.add_row(
            f'{idx:{_SERIAL_WIDTH}d}',
            row.raw_title, row.raw_artist, row.raw_album,
            row.year, format_duration(seconds=row.duration_seconds),
            _display_path(file_path=row.file_path, month_folder=row.month_folder),
        )
    console.print(table)


def _add_multi_month_table(console: Console, rows: list[MultiMonthRow]) -> None:
    table = Table(
        title=f'{len(rows)} songs are in 01-Singles-All AND in multiple month folders',
        title_justify='left', show_lines=False, header_style='bold cyan', expand=True,
    )
    table.add_column('#', justify='right', width=_SERIAL_WIDTH, style='dim')
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Year', justify='right')
    table.add_column('Duration', justify='right')
    table.add_column('Found in', overflow='fold', ratio=3)
    for idx, row in enumerate(rows, start=1):
        table.add_row(
            f'{idx:{_SERIAL_WIDTH}d}',
            row.raw_title, row.raw_artist, row.raw_album,
            row.year, format_duration(seconds=row.duration_seconds),
            _format_folders(folders=row.folders),
        )
    console.print(table)


def _add_untagged_table(console: Console, rows: list[UntaggedRow]) -> None:
    table = Table(
        title=f'{len(rows)} files are untagged (missing title and/or artist)',
        title_justify='left', show_lines=False, header_style='bold yellow', expand=True,
    )
    table.add_column('#', justify='right', width=_SERIAL_WIDTH, style='dim')
    table.add_column('File', overflow='fold', ratio=3)
    table.add_column('Missing fields')
    for idx, row in enumerate(rows, start=1):
        missing = missing_tag_fields(raw_title=row.raw_title, raw_artist=row.raw_artist)
        table.add_row(
            f'{idx:{_SERIAL_WIDTH}d}',
            _display_path(file_path=row.file_path, month_folder=row.month_folder),
            ', '.join(missing) if missing else '(none)',
        )
    console.print(table)


def render_console(
        console: Console,
        only_in_all: list[MatchedRow],
        only_in_months: list[MatchedRow],
        in_multiple_months: list[MultiMonthRow],
        untagged: list[UntaggedRow],
        title_prefix: str | None,
        total_month_songs: int = 0,
        range_active: bool = False,
        start_yyyymm: str = '',
        end_yyyymm: str = '',
) -> None:
    """Render the four-section report to the console.

    When range_active is True, the 'only_in_all' section is suppressed entirely
    (no table, no OK line) and a one-line notice is printed instead.
    """
    if title_prefix:
        console.print(f'[bold]Title-prefix filter is active:[/bold] {title_prefix!r}')

    if range_active:
        start_label = start_yyyymm or '-inf'
        end_label = end_yyyymm or '+inf'
        console.print(
            f"[bold]Month range is active:[/bold] {start_label}..{end_label}; "
            f"'only_in_all' section is suppressed."
        )
    elif only_in_all:
        _add_matched_table(
            console=console,
            title=f'{len(only_in_all)} songs are in 01-Singles-All AND missing from 03-Singles-by-Month/',
            rows=only_in_all,
        )
    else:
        console.print('[green]OK -- every tagged song in 01-Singles-All has a match under 03-Singles-by-Month/[/green]')

    if only_in_months:
        total_size = sum(row.size_bytes for row in only_in_months)
        _add_matched_table(
            console=console,
            title=(f'Only in 03-Singles-by-Month '
                   f'({len(only_in_months)} of {total_month_songs} songs are missing from '
                   f'01-Singles-All, total size {_format_size(size_bytes=total_size)})'),
            rows=only_in_months,
        )
    else:
        console.print('[green]OK -- every tagged song under 03-Singles-by-Month/ has a match in 01-Singles-All[/green]')

    if in_multiple_months:
        _add_multi_month_table(console=console, rows=in_multiple_months)
    else:
        console.print('[green]OK -- no song appears in multiple month folders[/green]')

    if untagged:
        _add_untagged_table(console=console, rows=untagged)
    else:
        console.print('[green]OK -- every file has title and artist tags[/green]')

    only_in_all_label = '-' if range_active else str(len(only_in_all))
    summary = (
        f'Only-in-all: {only_in_all_label} | '
        f'Months-only: {len(only_in_months)} | '
        f'Multi-month: {len(in_multiple_months)} | '
        f'Untagged: {len(untagged)}'
    )
    console.print(f'\n[bold]Summary:[/bold] {summary}')


def write_csv(
        csv_path: Path,
        only_in_all: list[MatchedRow],
        only_in_months: list[MatchedRow],
        in_multiple_months: list[MultiMonthRow],
        untagged: list[UntaggedRow],
) -> None:
    """Write the four-section report as a single CSV with a 'section' column."""
    with csv_path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['section', 'title', 'artist', 'album', 'year',
                         'duration', 'file_path', 'extra'])
        for matched in only_in_all:
            writer.writerow([
                'only_in_all',
                matched.raw_title, matched.raw_artist, matched.raw_album,
                matched.year, format_duration(seconds=matched.duration_seconds),
                _display_path(file_path=matched.file_path, month_folder=matched.month_folder), '',
            ])
        for matched in only_in_months:
            writer.writerow([
                'only_in_months',
                matched.raw_title, matched.raw_artist, matched.raw_album,
                matched.year, format_duration(seconds=matched.duration_seconds),
                _display_path(file_path=matched.file_path, month_folder=matched.month_folder), '',
            ])
        for multi in in_multiple_months:
            writer.writerow([
                'in_multiple_months',
                multi.raw_title, multi.raw_artist, multi.raw_album,
                multi.year, format_duration(seconds=multi.duration_seconds),
                _display_path(file_path=multi.file_path, month_folder=None),
                _format_folders(folders=multi.folders),
            ])
        for untag in untagged:
            missing = missing_tag_fields(raw_title=untag.raw_title, raw_artist=untag.raw_artist)
            extra = 'missing: ' + ' '.join(missing) if missing else ''
            writer.writerow([
                'untagged',
                untag.raw_title, untag.raw_artist, untag.raw_album,
                '', '', _display_path(file_path=untag.file_path, month_folder=untag.month_folder),
                extra,
            ])
