#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
Interactively inspect a range of dupe-staging groups without a tag app.

Given a range of ``Staging-Dupes/grp-NNNN/`` folders, this prints the files' tags
in a table grouped by song, builds a cover-art collage (a labelled thumbnail per
file) so they can be compared at a glance, then prompts per file for an action:
play the audio (``a``), next/prev (``n``/``p``), view that file's art (``v``), or a
verdict -- ``o`` (original) / ``d`` (duplicate) / ``c`` (clear). It only writes the
verdict into the Copyright tag; run ``main-check-greek-singles.py --post-inspection``
afterwards to actually move/restore the files. Logic lives in
``funcs_check_greek_singles/inspect_groups.py``.

Built for the Windows + PyCharm Run-window workflow (plain flushed input(), no
prompt_toolkit). Run with --help for usage; --version for the build timestamp.
"""
import argparse
import logging
import os
import platform
import shutil
import subprocess
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

from funcs_check_greek_singles.config import (  # noqa: E402
    STAGING_DIRNAME, VERDICT_DUPLICATE, VERDICT_ORIGINAL,
)
from funcs_check_greek_singles.file_actions import parse_group_range  # noqa: E402
from funcs_check_greek_singles.inspect_groups import (  # noqa: E402
    InspectFile, InspectGroup, build_collage, iter_files, load_groups, set_verdict,
)
from funcs_check_greek_singles.normalize import format_duration  # noqa: E402
from funcs_check_greek_singles.state_tag import (  # noqa: E402
    VERDICT_AMBIGUOUS, VERDICT_PENDING, clear_state,
)
from funcs_utils import setup_logging  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-05-26-1610'

SINGLES_ROOT_DEFAULT = Path.home() / 'Music' / 'Greek'
IMAGES_DIRNAME = 'Dupes-images'
DEFAULT_CONSOLE_WIDTH = 140

# Default audio player per platform (override with --player). WSL is grouped with
# Windows: the music is on the C: drive and foobar2000 is the Windows player. All
# three named players are single-instance, so launching '<player> <file>' plays
# immediately and routes to the already-open window instead of spawning a new one.
_WINDOWS_PLAYER_CANDIDATES = (r'C:\Program Files\foobar2000\foobar2000.exe', 'foobar2000.exe')
_LINUX_PLAYER_CANDIDATES = ('audacious', 'rhythmbox')

# JPEG / PNG magic bytes, for naming a single file's art dump in the 'v' action.
_JPEG_MAGIC = b'\xff\xd8\xff'
_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

# Rich styling for the Verdict column, keyed by classify_verdict() result.
_VERDICT_STYLE = {
    VERDICT_ORIGINAL: '[green]original[/green]',
    VERDICT_DUPLICATE: '[red]duplicate[/red]',
    VERDICT_AMBIGUOUS: '[yellow]ambiguous[/yellow]',
    VERDICT_PENDING: '[dim]-[/dim]',
}

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. argv=None uses sys.argv[1:]."""
    parser = argparse.ArgumentParser(
        description='Interactively inspect a range of Staging-Dupes/grp-NNNN folders '
                    'and record o/d verdicts.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument(
        'groups',
        help="Group range to inspect: 'N1-N2', 'N1,N2', or a single 'N' (e.g. 8-9).")
    parser.add_argument(
        '--root', type=Path, default=SINGLES_ROOT_DEFAULT,
        help='Greek music root (contains the staging folder). Default: %(default)s')
    parser.add_argument(
        '--staging-dir', type=Path, default=None,
        help=f'Folder holding the grp-NNNN subfolders. Default: <root>/{STAGING_DIRNAME}.')
    parser.add_argument(
        '--images-dir', type=Path, default=None,
        help=f'Folder for the cover-art collage. Default: <root>/{IMAGES_DIRNAME}.')
    parser.add_argument(
        '--player', type=Path, default=None,
        help='Audio player executable for the (a)ction. Default: foobar2000 on '
             'Windows/WSL, audacious/rhythmbox on Linux, else the OS default app.')
    parser.add_argument(
        '--no-collage', action='store_true',
        help='Do not build/open the cover-art collage (the per-file v action still works).')
    parser.add_argument(
        '--width', type=int, default=None,
        help=f'Console width override. Default: auto-detect (fallback {DEFAULT_CONSOLE_WIDTH}).')
    parser.add_argument(
        '--verbose', action='store_true', help='Enable DEBUG-level logging.')
    return parser.parse_args(argv)


def _parse_groups_arg(value: str) -> tuple[int, int]:
    """Parse the positional group range, accepting 'N1-N2', 'N1,N2' or a single 'N'."""
    normalized = value.strip().replace('-', ',')
    if ',' not in normalized:
        normalized = f'{normalized},{normalized}'
    return parse_group_range(value=normalized)


def _is_windows() -> bool:
    """True when running on native Windows."""
    return sys.platform == 'win32'


def _is_wsl() -> bool:
    """True when running under WSL (Linux kernel reporting a Microsoft build)."""
    return 'microsoft' in platform.uname().release.lower()


def _to_windows_path(path: Path) -> str:
    """Translate a WSL path to its Windows form via wslpath; fall back to the input."""
    result = subprocess.run(  # nosec
        ['wslpath', '-w', str(path)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
    return result.stdout.strip() or str(path)


def _wsl_mount(windows_path: str) -> str | None:
    """Map a 'C:\\...' Windows path to an existing /mnt/<drive>/... WSL path, or None."""
    if len(windows_path) < 2 or windows_path[1] != ':':
        return None
    rest = windows_path[2:].lstrip('\\/').replace('\\', '/')
    mounted = Path(f'/mnt/{windows_path[0].lower()}/{rest}')
    return str(mounted) if mounted.is_file() else None


def _resolve_player(arg: Path | None) -> str | None:
    """Return a launchable player command for this platform, or None if none is found."""
    if arg is not None:
        return str(arg)
    on_windows_family = _is_windows() or _is_wsl()
    candidates = _WINDOWS_PLAYER_CANDIDATES if on_windows_family else _LINUX_PLAYER_CANDIDATES
    for candidate in candidates:
        if _is_wsl():
            mounted = _wsl_mount(windows_path=candidate)
            if mounted is not None:
                return mounted
        elif Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found is not None:
            return found
    return None


def _open_path(path: Path) -> None:
    """Open a file with the OS default application (collage / single-art viewer)."""
    # pylint: disable=consider-using-with
    startfile = getattr(os, 'startfile', None)
    if _is_windows() and startfile is not None:
        startfile(str(path))  # pylint: disable=not-callable
        return
    if _is_wsl():
        subprocess.Popen(['cmd.exe', '/c', 'start', '', _to_windows_path(path=path)])  # nosec
        return
    subprocess.Popen(['xdg-open', str(path)])  # nosec


def _play_file(player: str | None, audio_path: Path) -> None:
    """Play one file: via the resolved player, or the OS default app as a fallback."""
    # pylint: disable=consider-using-with
    if player is None:
        _open_path(path=audio_path)
        return
    arg = _to_windows_path(path=audio_path) if _is_wsl() else str(audio_path)
    subprocess.Popen([player, arg])  # nosec


def _art_extension(data: bytes) -> str:
    """Return a sensible file extension for raw cover-art bytes (jpg / png / img)."""
    if data.startswith(_JPEG_MAGIC):
        return 'jpg'
    if data.startswith(_PNG_MAGIC):
        return 'png'
    return 'img'


def _show_file_art(file: InspectFile, images_dir: Path) -> None:
    """Dump one file's embedded art to images_dir and open it, or note its absence."""
    if file.art is None:
        print(f'  {file.label}: no cover art')
        return
    images_dir.mkdir(parents=True, exist_ok=True)
    out = images_dir / f'_view-{file.group_name}-{file.label}.{_art_extension(data=file.art)}'
    out.write_bytes(file.art)
    _open_path(path=out)


def _verdict_cell(verdict: str) -> str:
    """Render a classify_verdict() result as a styled Rich cell."""
    return _VERDICT_STYLE.get(verdict, verdict)


def render_table(console: Console, groups: list[InspectGroup]) -> None:
    """Print one row per file, grouped by song, in the same style as the staging table."""
    total = sum(len(group.files) for group in groups)
    table = Table(
        title=f'{len(groups)} group(s) ({total} files) to inspect',
        title_justify='left', show_lines=False, header_style='bold magenta', expand=True)
    table.add_column('#', justify='right', width=3, style='dim')
    table.add_column('Label', no_wrap=True)
    table.add_column('Group', overflow='fold')
    table.add_column('Title', overflow='fold', ratio=2)
    table.add_column('Artist', overflow='fold', ratio=2)
    table.add_column('Album', overflow='fold', ratio=2)
    table.add_column('Year', justify='right')
    table.add_column('Duration', justify='right')
    table.add_column('Art', justify='center')
    table.add_column('Verdict', no_wrap=True)
    table.add_column('File', overflow='fold', ratio=3)
    flat_index = 0
    for group in groups:
        for member_no, file in enumerate(group.files, start=1):
            flat_index += 1
            song = file.song
            table.add_row(
                str(flat_index), file.label,
                file.group_name if member_no == 1 else '',
                song.raw_title, song.raw_artist, song.raw_album, song.year,
                format_duration(seconds=song.duration_seconds),
                '[green]✓[/green]' if file.has_art else '[red]✗[/red]',
                _verdict_cell(verdict=file.current_verdict),
                file.path.name,
            )
        table.add_section()
    console.print(table)


def _prompt(message: str) -> str:
    """Print a flushed prompt and read one stripped, lower-cased reply (EOF -> 'q')."""
    print(message, end='', flush=True)
    try:
        return input().strip().lower()
    except EOFError:
        return 'q'


def run_inspection_loop(files: list[InspectFile], *, player: str | None,
                        images_dir: Path) -> dict[str, int]:
    """Drive the per-file action loop; write verdicts; return per-action counts.

    Navigation: a=play, v=view art, n/blank=next, p=prev, d/o=verdict (advance),
    c=clear verdict (stay), q/EOF=quit. The verdict column shown in the prompt tracks
    edits made during the loop.
    """
    counts = {'original': 0, 'duplicate': 0, 'cleared': 0}
    verdicts = [file.current_verdict for file in files]
    index = 0
    while 0 <= index < len(files):
        file = files[index]
        reply = _prompt(message=f'{index + 1}-{file.label} [{verdicts[index]}]? <a/n/p/d/o/c/v/q>: ')
        if reply == 'q':
            break
        if reply == 'a':
            _play_file(player=player, audio_path=file.path)
        elif reply == 'v':
            _show_file_art(file=file, images_dir=images_dir)
        elif reply == 'p':
            index = max(0, index - 1)
        elif reply in ('', 'n'):
            index += 1
        elif reply == 'd':
            set_verdict(file_path=file.path, verdict=VERDICT_DUPLICATE)
            verdicts[index] = VERDICT_DUPLICATE
            counts['duplicate'] += 1
            index += 1
        elif reply == 'o':
            set_verdict(file_path=file.path, verdict=VERDICT_ORIGINAL)
            verdicts[index] = VERDICT_ORIGINAL
            counts['original'] += 1
            index += 1
        elif reply == 'c':
            clear_state(file_path=file.path, field='verdict')
            verdicts[index] = VERDICT_PENDING
            counts['cleared'] += 1
        else:
            print(f'  unrecognized: {reply!r} (use a/n/p/d/o/c/v/q)')
    pending = sum(1 for verdict in verdicts if verdict == VERDICT_PENDING)
    counts['pending'] = pending
    return counts


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code (0 ok, 2 usage / missing staging dir)."""
    args = parse_args(argv=argv)
    setup_logging(verbose=args.verbose, log_to_file=True, log_dir=_PROJECT_ROOT / 'Logs')
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8', errors='replace')

    try:
        group_range = _parse_groups_arg(value=args.groups)
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    staging_dir = (args.staging_dir or (args.root.resolve() / STAGING_DIRNAME)).resolve()
    if not staging_dir.is_dir():
        logger.error(f'Staging folder does not exist or is not a directory: {staging_dir}')
        return 2
    images_dir = (args.images_dir or (args.root.resolve() / IMAGES_DIRNAME)).resolve()

    groups = load_groups(staging_dir=staging_dir, group_range=group_range)
    files = iter_files(groups=groups)
    width = args.width or shutil.get_terminal_size(fallback=(DEFAULT_CONSOLE_WIDTH, 24)).columns
    console = Console(force_terminal=True, width=width)
    if not files:
        console.print(f'No files found in groups {group_range[0]}-{group_range[1]} '
                      f'under {staging_dir}.')
        return 0

    render_table(console=console, groups=groups)
    if not args.no_collage:
        collage = images_dir / f'grp-{group_range[0]:04d}-to-grp-{group_range[1]:04d}.png'
        try:
            build_collage(groups=groups, out_path=collage)
            console.print(f'Collage: {collage}')
            _open_path(path=collage)
        except RuntimeError as exc:
            logger.warning(f'collage skipped: {exc}')

    counts = run_inspection_loop(
        files=files, player=_resolve_player(arg=args.player), images_dir=images_dir)
    console.print(
        f"\n[bold]Done:[/bold] original: {counts['original']} | duplicate: "
        f"{counts['duplicate']} | cleared: {counts['cleared']} | still pending: "
        f"{counts['pending']}")
    console.print('[dim]Apply with:[/dim] main-check-greek-singles.py --post-inspection '
                  f'milk-run --staging-groups {group_range[0]},{group_range[1]}  '
                  '[dim](try dry-run first)[/dim]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
