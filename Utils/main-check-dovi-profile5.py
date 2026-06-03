#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Detect whether a video file (or directory of videos) is Dolby Vision profile 5.

DoVi profile 5 cannot be played by Plex on some devices. Exits 1 when the path is
(or contains) a profile-5 video ("bad"), 0 otherwise ("good").
"""
import argparse
import sys
from pathlib import Path

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from funcs_for_qb_notify.dovi import path_is_bad  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-06-03-1700'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. argv=None uses sys.argv[1:].

    Args:
        argv: Optional argument list (for testing).

    Returns:
        argparse.Namespace: Parsed arguments with the 'path' attribute.
    """
    parser = argparse.ArgumentParser(
        description='Detect Dolby Vision profile 5 (problematic for Plex) in a file or directory.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('path', type=Path, help='Video file or directory to check')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Print a one-line verdict and exit 1 (bad) or 0 (good).

    Args:
        argv: Optional argument list (for testing).

    Raises:
        SystemExit: 1 if the path is/contains DoVi profile 5, else 0.
    """
    args = parse_args(argv)
    if not args.path.exists():
        print(f'Error: {args.path} does not exist', file=sys.stderr)
        raise SystemExit(2)

    if path_is_bad(path=args.path):
        print(f'BAD: DoVi profile 5 detected in {args.path}')
        raise SystemExit(1)
    print(f'good: no DoVi profile 5 in {args.path}')
    raise SystemExit(0)


if __name__ == '__main__':
    main()
