#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Step-1 probe: discover which MP4 atoms VLC shows in its *General* (primary) tab.

Writes a distinct PROBE-<atom> sentinel to each candidate MP4 atom on a copy of a real
.mp4, so opening the copy in VLC -> Tools -> Media Information reveals exactly which atom
feeds which General-tab field (Title, Artist, Album, Date, Comment, Copyright, Publisher,
Encoded by, Setting, ...). The goal is to land as many of our six values as possible in the
General tab rather than the secondary Metadata tab.

The copy is written under Tests/ so nothing is created in the git-tracked main dirs.

Usage:
    python Tests-Standalone/probe-video-tags-vlc.py /path/to/real.mp4
"""
import argparse
import sys
from pathlib import Path

from mutagen.mp4 import MP4

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _PROJECT_ROOT / 'Tests'

# atom -> distinct sentinel. Each sentinel embeds the atom's fourcc so the VLC field that
# shows it identifies the atom. Includes the six already-confirmed atoms (for context) plus
# General-tab candidates: the ©-prefixed Copyright/Publisher/Encoded-by/Setting variants VLC
# is believed to read (the bare 'cprt'/iTunes-freeform forms only surfaced in the Metadata tab).
_PROBE_ATOMS = {
    '\xa9nam': 'PROBE-nam(title)',
    '\xa9ART': 'PROBE-ART(artist)',
    '\xa9alb': 'PROBE-alb(album)',
    '\xa9day': 'PROBE-day(date)',
    '\xa9cmt': 'PROBE-cmt(comment)',
    '\xa9wrt': 'PROBE-wrt(writer/composer)',
    '\xa9gen': 'PROBE-gen(genre)',
    'aART': 'PROBE-aART(albumartist)',
    '\xa9too': 'PROBE-too(encodingtool)',
    '\xa9enc': 'PROBE-enc(setting/encodedby)',
    '\xa9cpy': 'PROBE-cpy(copyright)',
    'cprt': 'PROBE-cprt(copyright)',
    '\xa9pub': 'PROBE-pub(publisher)',
    'desc': 'PROBE-desc(description)',
    'ldes': 'PROBE-ldes(longdesc)',
    '\xa9url': 'PROBE-url',
    '\xa9grp': 'PROBE-grp(grouping)',
    'tvsh': 'PROBE-tvsh(show)',
    '\xa9dir': 'PROBE-dir(director)',
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list (for testing).

    Returns:
        argparse.Namespace: Parsed arguments with the 'source' attribute.
    """
    parser = argparse.ArgumentParser(description='Write sentinel tags to a .mp4 copy for VLC inspection.')
    parser.add_argument('source', type=Path, help='A real .mp4 video to copy and tag')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Copy the source .mp4 into Tests/ and write a distinct sentinel to each candidate atom.

    Args:
        argv: Optional argument list (for testing).

    Raises:
        SystemExit: 2 if the source file does not exist or is not a .mp4.
    """
    args = parse_args(argv)
    source = args.source
    if not source.is_file() or source.suffix.lower() != '.mp4':
        print(f'Error: {source} is not an existing .mp4 file', file=sys.stderr)
        raise SystemExit(2)

    _TESTS_DIR.mkdir(exist_ok=True)
    target = _TESTS_DIR / f'probe-{source.stem}.mp4'
    target.write_bytes(source.read_bytes())

    audio = MP4(target)
    for atom, value in _PROBE_ATOMS.items():
        audio[atom] = [value]
    audio.save()

    print(f'Wrote {len(_PROBE_ATOMS)} sentinel atoms to: {target}')
    print('Open it in VLC -> Tools -> Media Information -> General tab and report which')
    print('PROBE-<atom>(...) values appear and under which field label.')


if __name__ == '__main__':
    main()
