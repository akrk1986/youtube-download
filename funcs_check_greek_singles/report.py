"""Console (Rich) + CSV report rendering for the cross-checker."""
import csv
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.table import Table

from funcs_check_greek_singles.normalize import format_duration, missing_tag_fields


def _format_folders(folders: str | None) -> str:
    if not folders:
        return ''
    return '; '.join(part.strip() for part in folders.split(','))


def _add_matched_table(console: Console, title: str, rows: list[sqlite3.Row]) -> None:
    table = Table(title=title, show_lines=False, header_style='bold cyan')
    table.add_column('Title', overflow='fold')
    table.add_column('Artist', overflow='fold')
    table.add_column('Album', overflow='fold')
    table.add_column('Year', justify='right')
    table.add_column('Duration', justify='right')
    table.add_column('File', overflow='fold')
    for row in rows:
        table.add_row(
            row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
            row['year'] or '', format_duration(seconds=row['duration_seconds']),
            row['file_path'],
        )
    console.print(table)


def _add_multi_month_table(console: Console, rows: list[sqlite3.Row]) -> None:
    table = Table(
        title=f'In 01-Singles-All AND in multiple month folders ({len(rows)} songs)',
        show_lines=False, header_style='bold cyan',
    )
    table.add_column('Title', overflow='fold')
    table.add_column('Artist', overflow='fold')
    table.add_column('Album', overflow='fold')
    table.add_column('Year', justify='right')
    table.add_column('Duration', justify='right')
    table.add_column('Found in', overflow='fold')
    for row in rows:
        table.add_row(
            row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
            row['year'] or '', format_duration(seconds=row['duration_seconds']),
            _format_folders(folders=row['folders']),
        )
    console.print(table)


def _add_untagged_table(console: Console, rows: list[sqlite3.Row]) -> None:
    table = Table(
        title=f'Untagged ({len(rows)} files: missing title and/or artist)',
        show_lines=False, header_style='bold yellow',
    )
    table.add_column('File', overflow='fold')
    table.add_column('Missing fields')
    for row in rows:
        missing = missing_tag_fields(raw_title=row['raw_title'] or '', raw_artist=row['raw_artist'] or '')
        table.add_row(row['file_path'], ', '.join(missing) if missing else '(none)')
    console.print(table)


def render_console(
        console: Console,
        only_in_all: list[sqlite3.Row],
        only_in_months: list[sqlite3.Row],
        in_multiple_months: list[sqlite3.Row],
        untagged: list[sqlite3.Row],
        title_prefix: str | None,
        range_active: bool = False,
        start_yyyymm: str = '',
        end_yyyymm: str = '',
) -> None:
    """Render the four-section report to the console.

    When range_active is True, the 'only_in_all' section is suppressed entirely
    (no table, no OK line) and a one-line notice is printed instead.
    """
    if title_prefix:
        console.print(f'[bold]Title-prefix filter active:[/bold] {title_prefix!r}')

    if range_active:
        start_label = start_yyyymm or '-inf'
        end_label = end_yyyymm or '+inf'
        console.print(
            f"[bold]Month range active:[/bold] {start_label}..{end_label}; "
            f"'only_in_all' section suppressed."
        )
    elif only_in_all:
        _add_matched_table(
            console=console,
            title=f'Only in 01-Singles-All ({len(only_in_all)} songs)',
            rows=only_in_all,
        )
    else:
        console.print('[green]OK -- every tagged song in 01-Singles-All has a match under 03-Singles-by-Month/[/green]')

    if only_in_months:
        _add_matched_table(
            console=console,
            title=f'Only in 03-Singles-by-Month ({len(only_in_months)} songs)',
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
        only_in_all: list[sqlite3.Row],
        only_in_months: list[sqlite3.Row],
        in_multiple_months: list[sqlite3.Row],
        untagged: list[sqlite3.Row],
) -> None:
    """Write the four-section report as a single CSV with a 'section' column."""
    with csv_path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['section', 'title', 'artist', 'album', 'year',
                         'duration', 'file_path', 'extra'])
        for row in only_in_all:
            writer.writerow([
                'only_in_all',
                row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
                row['year'] or '', format_duration(seconds=row['duration_seconds']),
                row['file_path'], '',
            ])
        for row in only_in_months:
            writer.writerow([
                'only_in_months',
                row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
                row['year'] or '', format_duration(seconds=row['duration_seconds']),
                row['file_path'], '',
            ])
        for row in in_multiple_months:
            writer.writerow([
                'in_multiple_months',
                row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
                row['year'] or '', format_duration(seconds=row['duration_seconds']),
                row['file_path'], _format_folders(folders=row['folders']),
            ])
        for row in untagged:
            missing = missing_tag_fields(raw_title=row['raw_title'] or '', raw_artist=row['raw_artist'] or '')
            extra = 'missing: ' + ' '.join(missing) if missing else ''
            writer.writerow([
                'untagged',
                row['raw_title'] or '', row['raw_artist'] or '', row['raw_album'] or '',
                '', '', row['file_path'], extra,
            ])
