"""Console (Rich) + CSV report rendering for the cross-checker."""
import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from funcs_check_greek_singles.config import DURATION_MATCH_MARGIN_SECONDS
from funcs_check_greek_singles.models import (
    CrossMonthDupRow, InFolderDupRow, MatchedRow, MultiMonthRow, StagingGroup, UntaggedRow,
)
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


def _add_in_folder_dup_table(console: Console, rows: list[InFolderDupRow]) -> None:
    total_files = sum(row.dup_count for row in rows)
    table = Table(
        title=f'{len(rows)} clusters ({total_files} files) are duplicate within a single folder',
        title_justify='left', show_lines=False, header_style='bold magenta', expand=True,
    )
    table.add_column('Folder', overflow='fold', ratio=2)
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('#', justify='right', width=3, style='dim')
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Duration', justify='right')
    table.add_column('File', overflow='fold', ratio=3)
    for row in rows:
        folder = 'All/' if row.month_folder is None else f'{row.month_folder}/'
        for dupe_no, member in enumerate(row.members, start=1):
            first = dupe_no == 1
            table.add_row(
                folder if first else '',
                row.raw_title if first else '',
                row.raw_artist if first else '',
                str(dupe_no),
                member.raw_album,
                format_duration(seconds=member.duration_seconds),
                Path(member.file_path).name,
            )
        table.add_section()
    console.print(table)


def _add_cross_month_dup_table(console: Console, rows: list[CrossMonthDupRow]) -> None:
    total_files = sum(row.dup_count for row in rows)
    table = Table(
        title=f'{len(rows)} clusters ({total_files} files) are duplicate across months in the range',
        title_justify='left', show_lines=False, header_style='bold magenta', expand=True,
    )
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('#', justify='right', width=3, style='dim')
    table.add_column('Month', overflow='fold', ratio=2)
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Duration', justify='right')
    table.add_column('File', overflow='fold', ratio=3)
    for row in rows:
        for dupe_no, member in enumerate(row.members, start=1):
            first = dupe_no == 1
            table.add_row(
                row.raw_title if first else '',
                row.raw_artist if first else '',
                str(dupe_no),
                member.month_folder or '',
                member.raw_album,
                format_duration(seconds=member.duration_seconds),
                Path(member.file_path).name,
            )
        table.add_section()
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


def render_staging_groups(console: Console, groups: list[StagingGroup]) -> None:
    """Print the dupe groups being staged, one row per file, grouped by folder.

    Columns: Group | # | Folder | Title | Artist | Album | Duration | File. The
    group folder + title/artist print on the first row of each group; a horizontal
    delimiter separates groups (same look as the main report).
    """
    total_files = sum(len(group.members) for group in groups)
    table = Table(
        title=f'{len(groups)} dupe group(s) ({total_files} files) staged into grp-NNNN folders',
        title_justify='left', show_lines=False, header_style='bold magenta', expand=True,
    )
    table.add_column('Group', overflow='fold')
    table.add_column('#', justify='right', width=3, style='dim')
    table.add_column('Folder', overflow='fold', ratio=2)
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Duration', justify='right')
    table.add_column('File', overflow='fold', ratio=3)
    for group in groups:
        for member_no, member in enumerate(group.members, start=1):
            first = member_no == 1
            folder = 'All/' if member.month_folder is None else f'{member.month_folder}/'
            table.add_row(
                group.folder_name if first else '',
                str(member_no),
                folder,
                group.raw_title if first else '',
                group.raw_artist if first else '',
                member.raw_album,
                format_duration(seconds=member.duration_seconds),
                Path(member.file_path).name,
            )
        table.add_section()
    console.print(table)


def render_console(
        console: Console,
        only_in_all: list[MatchedRow],
        only_in_months: list[MatchedRow],
        in_multiple_months: list[MultiMonthRow],
        untagged: list[UntaggedRow],
        in_folder_duplicates: list[InFolderDupRow],
        cross_month_duplicates: list[CrossMonthDupRow],
        title_prefix: str | None,
        total_month_songs: int = 0,
        range_active: bool = False,
        start_yyyymm: str = '',
        end_yyyymm: str = '',
        dupes_scope: str | None = None,
) -> None:
    """Render the report to the console.

    When range_active is True, the 'only_in_all' section is suppressed entirely
    (no table, no OK line) and a one-line notice is printed instead.
    dupes_scope selects a dupe-only mode: 'folder' renders just the in-folder
    section, 'range' renders just the cross-month section; None renders the full
    five-section report (no cross-month section).
    """
    if title_prefix:
        console.print(f'[bold]Title-prefix filter is active:[/bold] {title_prefix!r}')

    if dupes_scope == 'folder':
        if in_folder_duplicates:
            _add_in_folder_dup_table(console=console, rows=in_folder_duplicates)
        else:
            console.print('[green]OK -- no duplicate files within a single folder[/green]')
        console.print(f'\n[bold]Summary:[/bold] Folder-dups: {len(in_folder_duplicates)}')
        return

    if dupes_scope == 'range':
        console.print(f'[bold]Duration margin:[/bold] {DURATION_MATCH_MARGIN_SECONDS} secs')
        if cross_month_duplicates:
            _add_cross_month_dup_table(console=console, rows=cross_month_duplicates)
        else:
            console.print('[green]OK -- no duplicate files across months in the range[/green]')
        console.print(f'\n[bold]Summary:[/bold] Cross-month dupes: {len(cross_month_duplicates)}')
        return

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

    if in_folder_duplicates:
        _add_in_folder_dup_table(console=console, rows=in_folder_duplicates)
    else:
        console.print('[green]OK -- no duplicate files within a single folder[/green]')

    only_in_all_label = '-' if range_active else str(len(only_in_all))
    summary = (
        f'Only-in-all: {only_in_all_label} | '
        f'Months-only: {len(only_in_months)} | '
        f'Multi-month: {len(in_multiple_months)} | '
        f'Untagged: {len(untagged)} | '
        f'Folder-dups: {len(in_folder_duplicates)}'
    )
    console.print(f'\n[bold]Summary:[/bold] {summary}')


def write_csv(
        csv_path: Path,
        only_in_all: list[MatchedRow],
        only_in_months: list[MatchedRow],
        in_multiple_months: list[MultiMonthRow],
        untagged: list[UntaggedRow],
        in_folder_duplicates: list[InFolderDupRow],
        cross_month_duplicates: list[CrossMonthDupRow],
) -> None:
    """Write the report as a single CSV with a 'section' column."""
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
        for dup in in_folder_duplicates:
            folder_label = 'All' if dup.month_folder is None else dup.month_folder
            for member in dup.members:
                writer.writerow([
                    'in_folder_duplicates',
                    dup.raw_title, dup.raw_artist, member.raw_album,
                    '', format_duration(seconds=member.duration_seconds),
                    _display_path(file_path=member.file_path, month_folder=dup.month_folder),
                    f'cluster: {dup.dup_count} files in {folder_label}',
                ])
        for cross in cross_month_duplicates:
            for member in cross.members:
                writer.writerow([
                    'cross_month_duplicates',
                    cross.raw_title, cross.raw_artist, member.raw_album,
                    '', format_duration(seconds=member.duration_seconds),
                    _display_path(file_path=member.file_path, month_folder=member.month_folder),
                    f'cluster: {cross.dup_count} files across {cross.distinct_months} months',
                ])
