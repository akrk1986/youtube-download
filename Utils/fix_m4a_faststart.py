"""
Bulk-fix M4A files where the moov atom comes after the mdat atom.

Hardware players (e.g. HiBy M300) parse the moov atom to read metadata. When
moov is at the end of a large file, the player may fail to read tags. ffmpeg's
-movflags +faststart relocates moov before mdat with a zero-quality-loss remux.
"""
import argparse
import sys
from pathlib import Path

from common_av.ffmpeg import get_ffmpeg_paths
from common_av.m4a import apply_faststart, needs_faststart


def main() -> None:
    """Run the faststart bulk-fix CLI."""
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

    ffmpeg = args.ffmpeg or get_ffmpeg_paths()[0]

    glob = args.folder.rglob('*.m4a') if args.recursive else args.folder.glob('*.m4a')
    files = sorted(glob, key=lambda p: p.name.lower())

    if not files:
        print('No M4A files found.')
        return

    fixed = ok = errors = 0
    for f in files:
        try:
            if not needs_faststart(f):
                print(f'  OK       {f.name}')
                ok += 1
                continue
            if args.dry_run:
                print(f'  WOULD FIX {f.name}')
                fixed += 1
                continue
            apply_faststart(path=f, ffmpeg=ffmpeg)
            print(f'  FIXED    {f.name}')
            fixed += 1
        except Exception as e:
            print(f'  ERROR    {f.name}: {e}')
            errors += 1

    action = 'would fix' if args.dry_run else 'fixed'
    print(f'\nDone: {fixed} {action}, {ok} already OK, {errors} errors.')


if __name__ == '__main__':
    main()
