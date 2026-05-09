"""
Bulk-fix M4A files where the moov atom comes after the mdat atom.

Hardware players (e.g. HiBy M300) parse the moov atom to read metadata. When
moov is at the end of a large file, the player may fail to read tags. ffmpeg's
-movflags +faststart relocates moov before mdat with a zero-quality-loss remux.
"""
import argparse
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from funcs_for_audio_utils.conversion import get_ffmpeg_path


def _top_level_atoms(path: Path) -> list[str]:
    """Return ordered list of top-level atom names in the file."""
    atoms: list[str] = []
    with open(path, 'rb') as fh:
        while True:
            header = fh.read(8)
            if len(header) < 8:
                break
            size, name = struct.unpack('>I4s', header)
            atoms.append(name.decode('latin-1', errors='replace'))
            if size < 8:
                break
            fh.seek(size - 8, 1)
    return atoms


def _needs_faststart(path: Path) -> bool:
    """Return True if moov comes after mdat."""
    atoms = _top_level_atoms(path)
    if 'moov' in atoms and 'mdat' in atoms:
        return atoms.index('moov') > atoms.index('mdat')
    return False


def _apply_faststart(path: Path, ffmpeg: str) -> None:
    """Remux path in-place with -movflags +faststart. Raises on ffmpeg error."""
    with tempfile.NamedTemporaryFile(suffix='.m4a', dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(  # nosec B603
            [ffmpeg, '-y', '-i', str(path), '-c', 'copy',
             '-movflags', '+faststart', str(tmp_path)],
            capture_output=True,
            check=True,
        )
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fix M4A files where moov comes after mdat (hardware player tag issue).'
    )
    parser.add_argument('folder', type=Path, help='Folder to scan for M4A files')
    parser.add_argument('--recursive', action='store_true',
                        help='Also scan subdirectories (default: %(default)s)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report which files would be fixed without changing them')
    parser.add_argument('--ffmpeg', type=str, default=None,
                        help='Path to ffmpeg executable (default: auto-detected)')
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f'Error: not a directory: {args.folder}')
        sys.exit(1)

    ffmpeg = args.ffmpeg or get_ffmpeg_path()

    glob = args.folder.rglob('*.m4a') if args.recursive else args.folder.glob('*.m4a')
    files = sorted(glob, key=lambda p: p.name.lower())

    if not files:
        print('No M4A files found.')
        return

    fixed = ok = errors = 0
    for f in files:
        try:
            if not _needs_faststart(f):
                print(f'  OK       {f.name}')
                ok += 1
                continue
            if args.dry_run:
                print(f'  WOULD FIX {f.name}')
                fixed += 1
                continue
            _apply_faststart(path=f, ffmpeg=ffmpeg)
            print(f'  FIXED    {f.name}')
            fixed += 1
        except Exception as e:
            print(f'  ERROR    {f.name}: {e}')
            errors += 1

    action = 'would fix' if args.dry_run else 'fixed'
    print(f'\nDone: {fixed} {action}, {ok} already OK, {errors} errors.')


if __name__ == '__main__':
    main()
