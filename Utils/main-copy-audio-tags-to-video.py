#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Copy audio tags into sibling video files.

Reads the six metadata fields (title, artist, program->album, year, composer, comment)
from each .m4a/.mp3 in the audio folder and writes the equivalent MP4 atoms into the
same-basename .mp4 in the video folder, using mutagen (in place, no re-encode).

Runs on Linux/WSL and Windows (mutagen-only; no external tools required).
"""
import argparse
import logging
import sys
from pathlib import Path

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from funcs_copy_tags_to_video import (  # noqa: E402
    FieldChange,
    apply_tags_to_video,
    pair_audio_with_video,
    read_audio_tags,
)

# pylint: enable=wrong-import-position

VERSION = '2026-06-04-1634'
logger = logging.getLogger(__name__)


def _existing_directory(value: str) -> Path:
    """argparse type: resolve to a Path that must be an existing directory.

    Args:
        value: The raw command-line argument.

    Returns:
        Path: The validated directory path.

    Raises:
        argparse.ArgumentTypeError: If the path is not an existing directory.
    """
    path = Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"not a directory: '{value}'")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. argv=None uses sys.argv[1:].

    Args:
        argv: Optional argument list (for testing).

    Returns:
        argparse.Namespace: Parsed arguments (audio_dir, video_dir, dry_run).
    """
    parser = argparse.ArgumentParser(
        description='Copy audio tags (title/artist/program->album/year/composer/comment) '
                    'into sibling same-basename .mp4 video files.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('audio_dir', type=_existing_directory,
                        help='Folder containing the tagged .m4a/.mp3 audio files')
    parser.add_argument('video_dir', type=_existing_directory,
                        help='Sibling folder containing the .mp4 video files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show existing-vs-new values per field without writing')
    return parser.parse_args(argv)


def _print_pair(video_path: Path, changes: list[FieldChange], dry_run: bool) -> None:
    """Print a per-field existing-vs-new table for one audio/video pair.

    Args:
        video_path: The target video file.
        changes: The computed field changes, in display order.
        dry_run: Whether this is a dry run (affects the action label).
    """
    print(f'\n{video_path.name}')
    verb = 'would set' if dry_run else 'set'
    for change in changes:
        if change.will_write:
            note = f'  [{verb}]'
        elif not change.new_value:
            note = '  [skip: source empty]'
        else:
            note = '  [unchanged]'
        print(f"  {change.label:<22}: '{change.old_value}' -> '{change.new_value}'{note}")


def _print_pairing_table(pairs: list[tuple[Path, Path]],
                         audio_without_video: list[Path],
                         video_without_audio: list[Path]) -> None:
    """Print the audio<->video correspondence table; '<missing>' where either side is absent.

    Args:
        pairs: Matched (audio_path, video_path) pairs.
        audio_without_video: Audio files with no matching video.
        video_without_audio: Videos with no matching audio.
    """
    missing = '<missing>'
    rows = [(audio.name, video.name) for audio, video in pairs]
    rows += [(audio.name, missing) for audio in audio_without_video]
    rows += [(missing, video.name) for video in video_without_audio]

    audio_width = max([len('Audio')] + [len(audio) for audio, _ in rows])
    print(f'{"Audio":<{audio_width}}  Video')
    print(f'{"-" * audio_width}  {"-" * len("Video")}')
    for audio_name, video_name in rows:
        print(f'{audio_name:<{audio_width}}  {video_name}')


def main(argv: list[str] | None = None) -> None:
    """Pair audio with video files and copy tags, printing a summary.

    Args:
        argv: Optional argument list (for testing).

    Raises:
        SystemExit: 1 if no audio/video pairs are found.
    """
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    args = parse_args(argv)

    pairs, audio_without_video, video_without_audio = pair_audio_with_video(
        audio_dir=args.audio_dir, video_dir=args.video_dir)
    _print_pairing_table(pairs=pairs, audio_without_video=audio_without_video,
                         video_without_audio=video_without_audio)
    if not pairs:
        logger.error('No audio/video pairs found in %s and %s', args.audio_dir, args.video_dir)
        raise SystemExit(1)

    if args.dry_run:
        print('\nDRY RUN - no files will be modified.')

    written_fields = 0
    written_videos = 0
    for audio_path, video_path in pairs:
        tags = read_audio_tags(audio_path=audio_path)
        changes = apply_tags_to_video(video_path=video_path, tags=tags, dry_run=args.dry_run)
        _print_pair(video_path=video_path, changes=changes, dry_run=args.dry_run)
        pair_writes = sum(1 for change in changes if change.will_write)
        if pair_writes:
            written_videos += 1
            written_fields += pair_writes

    action = 'Would update' if args.dry_run else 'Updated'
    print(f'\n{action} {written_fields} field(s) across {written_videos} video(s); '
          f'{len(pairs)} pair(s), {len(audio_without_video)} audio without video, '
          f'{len(video_without_audio)} video without audio.')


if __name__ == '__main__':
    main()
