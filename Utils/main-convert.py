#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
Main staging script for copying audio tags between MP3 and M4A files,
and for converting FLAC files to MP3 or M4A.
Accepts --source parameter to specify source audio format (mp3, m4a, or flac).
"""
import argparse
import sys
import re
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC as MutagenFLAC
from mutagen.id3 import ID3, APIC, TENC
from mutagen.mp4 import MP4, MP4Cover
import arrow

from common_av.tags import AudioTags, MP4_LYRICS, write_mp3_tags, write_m4a_tags

from funcs_for_audio_utils import (
    convert_flac_to_m4a,
    convert_flac_to_mp3,
    convert_m4a_to_mp3,
    convert_mp3_to_m4a,
)
from project_defs import AUDIO_OUTPUT_DIR, AUDIO_OUTPUT_DIR_FLAC, AUDIO_OUTPUT_DIR_M4A


def normalize_year(year_str: str | int | None) -> str:
    """Normalize year to YYYY format using arrow for date parsing."""
    if not year_str:
        return ''

    year_str = str(year_str).strip()

    try:
        # Try parsing with arrow
        if len(year_str) == 8 and year_str.isdigit():
            # YYYYMMDD format
            parsed_date = arrow.get(year_str, 'YYYYMMDD')
            return str(parsed_date.year)
        if len(year_str) == 4 and year_str.isdigit():
            # Already YYYY format
            return year_str
        # Try to parse as date
        parsed_date = arrow.get(year_str)
        return str(parsed_date.year)
    except (arrow.parser.ParserMatchError, arrow.parser.ParserError):
        # Fallback to regex extraction
        match = re.search(r'\d{4}', year_str)
        if match:
            return match.group()

    return ''

def extract_mp3_tags(file_path: Path) -> dict[str, str] | None:
    """Extract relevant tags from MP3 file using EasyID3 and ID3."""
    try:
        # Use EasyID3 for most tags
        audio = EasyID3(file_path)
        year = normalize_year(year_str=audio.get('date', [''])[0])

        # Use raw ID3 for comment and TENC tags
        id3_audio = ID3(file_path)
        comment = ''
        if 'COMM::eng' in id3_audio:
            comment = str(id3_audio['COMM::eng'].text[0])
        elif id3_audio.getall('COMM'):
            # Get first comment if no English comment found
            comment = str(id3_audio.getall('COMM')[0].text[0])

        # Extract TENC (encoded by) tag
        encodedby = ''
        if 'TENC' in id3_audio:
            encodedby = str(id3_audio['TENC'].text[0]) if id3_audio['TENC'].text else ''

        return {
            'title': audio.get('title', [''])[0],
            'artist': audio.get('artist', [''])[0],
            'albumartist': audio.get('albumartist', [''])[0],
            'date': year,
            'album': audio.get('album', [''])[0],
            'tracknumber': audio.get('tracknumber', [''])[0],
            'comment': comment,
            'composer': audio.get('composer', [''])[0],
            'encodedby': encodedby
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error reading MP3 tags from {file_path}: {e}')
        return None

def extract_m4a_tags(file_path: Path) -> dict[str, str] | None:
    """Extract relevant tags from M4A file using MP4."""
    try:
        audio = MP4(file_path)
        year = normalize_year(
            year_str=audio.get('\xa9day', [''])[0] if audio.get('\xa9day') else ''
        )
        # Extract ©lyr (unsynced lyrics) tag - used to store original filename
        unsyncedlyrics = audio.get('\xa9lyr', [''])[0] if audio.get('\xa9lyr') else ''
        return {
            'title': audio.get('\xa9nam', [''])[0] if audio.get('\xa9nam') else '',
            'artist': audio.get('\xa9ART', [''])[0] if audio.get('\xa9ART') else '',
            'albumartist': audio.get('aART', [''])[0] if audio.get('aART') else '',
            'date': year,
            'album': audio.get('\xa9alb', [''])[0] if audio.get('\xa9alb') else '',
            'tracknumber': str(audio.get('trkn', [(0, 0)])[0][0])
            if audio.get('trkn') and audio.get('trkn')[0][0] > 0 else '',
            'comment': audio.get('\xa9cmt', [''])[0] if audio.get('\xa9cmt') else '',
            'composer': audio.get('\xa9wrt', [''])[0] if audio.get('\xa9wrt') else '',
            'encodedby': unsyncedlyrics
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error reading M4A tags from {file_path}: {e}')
        return None


def extract_flac_tags(file_path: Path) -> dict[str, str] | None:
    """Extract relevant tags from a FLAC file (Vorbis Comments)."""
    try:
        audio = MutagenFLAC(str(file_path))

        def _get(key: str) -> str:
            vals = audio.get(key.upper(), [])
            return vals[0] if vals else ''

        return {
            'title':       _get('title'),
            'artist':      _get('artist'),
            'albumartist': _get('albumartist'),
            'date':        normalize_year(year_str=_get('date')),
            'album':       _get('album'),
            'tracknumber': _get('tracknumber'),
            'comment':     _get('comment'),
            'composer':    _get('composer'),
            'encodedby':   _get('encodedby'),
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error reading FLAC tags from {file_path}: {e}')
        return None


def apply_mp3_tags(file_path: Path, tags: dict[str, str]) -> bool:
    """Apply tags to an MP3 file."""
    try:
        track_str = tags.get('tracknumber', '')
        audio_tags = AudioTags(
            title=tags.get('title', ''),
            artist=tags.get('artist', ''),
            album_artist=tags.get('albumartist', ''),
            album=tags.get('album', ''),
            year=tags.get('date', ''),
            track=int(track_str) if track_str.isdigit() else None,
            composer=tags.get('composer') or None,
            comment=tags.get('comment') or None,
        )
        write_mp3_tags(audio_path=file_path, tags=audio_tags, text_encoding=1)

        encodedby = tags.get('encodedby', '')
        if encodedby:
            id3_audio = ID3(file_path)
            id3_audio.add(TENC(encoding=3, text=encodedby))
            id3_audio.save(file_path)

        written = [k for k, v in tags.items() if v]
        if written:
            print(f'  Written tags: {", ".join(written)}')
        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error writing MP3 tags to {file_path}: {e}')
        return False

def apply_m4a_tags(file_path: Path, tags: dict[str, str]) -> bool:
    """Apply tags to an M4A file."""
    try:
        track_str = tags.get('tracknumber', '')
        audio_tags = AudioTags(
            title=tags.get('title', ''),
            artist=tags.get('artist', ''),
            album_artist=tags.get('albumartist', ''),
            album=tags.get('album', ''),
            year=tags.get('date', ''),
            track=int(track_str) if track_str.isdigit() else None,
            composer=tags.get('composer') or None,
            comment=tags.get('comment') or None,
        )
        write_m4a_tags(audio_path=file_path, tags=audio_tags)

        encodedby = tags.get('encodedby', '')
        if encodedby:
            audio = MP4(file_path)
            audio[MP4_LYRICS] = [encodedby]
            audio.save()

        written = [k for k, v in tags.items() if v]
        if written:
            print(f'  Written tags: {", ".join(written)}')
        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error writing M4A tags to {file_path}: {e}')
        return False

def _extract_cover_art(file_path: Path, fmt: str) -> tuple[bytes, str] | None:
    """Extract cover art from an audio file.

    Args:
        file_path: Path to the audio file.
        fmt: Audio format ('flac', 'm4a', or 'mp3').

    Returns:
        tuple[bytes, str] | None: Tuple of (image_bytes, mime_type) or None if not found.
    """
    try:
        if fmt == 'flac':
            audio = MutagenFLAC(str(file_path))
            # Prefer front-cover (type 3); fall back to first picture
            pics = [p for p in audio.pictures if p.type == 3] or list(audio.pictures)
            if not pics:
                return None
            pic = pics[0]
            return (pic.data, pic.mime)
        if fmt == 'm4a':
            m4a = MP4(file_path)
            covers = m4a.get('covr', [])
            if not covers:
                return None
            cover = covers[0]
            mime = 'image/png' if cover.imageformat == MP4Cover.FORMAT_PNG else 'image/jpeg'
            return (bytes(cover), mime)
        # mp3
        id3 = ID3(file_path)
        apic_frames = id3.getall('APIC')
        if not apic_frames:
            return None
        apic = apic_frames[0]
        return (apic.data, apic.mime)
    except Exception:  # pylint: disable=broad-exception-caught
        return None

def _apply_cover_art(file_path: Path, fmt: str, cover_data: bytes, mime: str) -> None:
    """Write cover art into an audio file.

    Args:
        file_path: Path to the target audio file.
        fmt: Target format ('mp3' or 'm4a').
        cover_data: Raw image bytes.
        mime: MIME type string (e.g. 'image/jpeg').
    """
    try:
        if fmt == 'mp3':
            id3 = ID3(file_path)
            id3.add(APIC(encoding=3, mime=mime, type=3, desc='', data=cover_data))
            id3.save(file_path)
        else:
            audio = MP4(file_path)
            imageformat = MP4Cover.FORMAT_PNG if mime == 'image/png' else MP4Cover.FORMAT_JPEG
            audio['covr'] = [MP4Cover(cover_data, imageformat=imageformat)]
            audio.save()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'  Warning: could not write cover art to {file_path.name}: {e}')

def _fill_missing_artist_tags(tags: dict[str, str]) -> None:
    """Copy artist to albumartist or vice versa if only one is set."""
    if tags.get('artist') and not tags.get('albumartist'):
        tags['albumartist'] = tags['artist']
    elif tags.get('albumartist') and not tags.get('artist'):
        tags['artist'] = tags['albumartist']

def _process_file(
    source_file: Path,
    target_file: Path,
    source_format: str,
    target_format: str,
    create_missing_files: bool,
) -> tuple[bool, bool, bool]:
    """Process one file: optionally convert, extract tags, apply tags.

    Args:
        source_file: Source audio file path.
        target_file: Target audio file path.
        source_format: Source audio format (e.g. 'mp3', 'm4a').
        target_format: Target audio format.
        create_missing_files: If True, convert source to target when target is missing.

    Returns:
        tuple[bool, bool, bool]: Tuple of (processed, warned, converted) booleans.
    """
    converted = False
    if not target_file.exists() or target_file.stat().st_size == 0:
        if create_missing_files:
            print(
                f"  Target file '{target_file.name}' does not exist or is empty, converting..."
            )
            if source_format == 'mp3':
                result = convert_mp3_to_m4a(mp3_file=source_file, m4a_file=target_file)
            elif source_format == 'm4a':
                result = convert_m4a_to_mp3(m4a_file=source_file, mp3_file=target_file)
            elif target_format == 'mp3':
                result = convert_flac_to_mp3(flac_file=source_file, mp3_file=target_file)
            else:
                result = convert_flac_to_m4a(flac_file=source_file, m4a_file=target_file)
            if result is None:
                print(f'  Failed to convert {source_file.name}')
                return False, True, False
            converted = True
        else:
            print(f"  WARNING: Target file '{target_file.name}' not found")
            return False, True, False

    # Extract tags from source file
    if source_format == 'mp3':
        tags = extract_mp3_tags(file_path=source_file)
    elif source_format == 'm4a':
        tags = extract_m4a_tags(file_path=source_file)
    else:
        tags = extract_flac_tags(file_path=source_file)

    if tags is None:
        return False, False, converted

    _fill_missing_artist_tags(tags=tags)

    # Apply tags to target file
    if target_format == 'mp3':
        success = apply_mp3_tags(file_path=target_file, tags=tags)
    else:
        success = apply_m4a_tags(file_path=target_file, tags=tags)

    # Copy cover art after tags are written (so ID3 save in apply_mp3_tags doesn't overwrite APIC)
    cover_art = _extract_cover_art(file_path=source_file, fmt=source_format)
    if cover_art:
        cover_data, mime = cover_art
        _apply_cover_art(file_path=target_file, fmt=target_format, cover_data=cover_data, mime=mime)

    return success, False, converted

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Copy songs and audio tags between MP3/M4A, or convert FLAC to MP3/M4A'
    )
    parser.add_argument(
        '--source',
        required=True,
        choices=['mp3', 'm4a', 'flac'],
        help='Source audio format (mp3, m4a, or flac)'
    )
    parser.add_argument(
        '--target',
        choices=['mp3', 'm4a', 'both'],
        help=(
            'Target format. Required when --source flac (mp3, m4a, or both). '
            'For --source mp3/m4a omit or specify the opposite format.'
        )
    )
    parser.add_argument(
        '--create-missing-files',
        action='store_true',
        help='Convert and create missing target files using ffmpeg before copying tags'
    )
    parser.add_argument(
        '--top-level-directory',
        type=lambda p: Path(p) if Path(p).exists() and Path(p).is_dir() else
                    parser.error(f"Directory '{p}' does not exist"),
        help='Top-level directory containing MP3, M4A and/or FLAC subfolders'
    )
    parser.add_argument(
        '--prefix',
        help="Prepend '<prefix> - ' to the target filename if not already present"
    )
    return parser.parse_args()

def main() -> int:  # pylint: disable=too-many-branches
    """Copy audio tags between source and target audio format directories."""
    args = parse_args()

    # Validate and resolve --target
    if args.source == 'flac':
        if not args.target:
            print('Error: --target is required when --source flac (mp3, m4a, or both)')
            return 1
    elif args.source == 'mp3':
        if args.target and args.target != 'm4a':
            print(f"Error: --target '{args.target}' is invalid when --source mp3 (use 'm4a' or omit)")
            return 1
        args.target = 'm4a'
    else:  # m4a
        if args.target and args.target != 'mp3':
            print(f"Error: --target '{args.target}' is invalid when --source m4a (use 'mp3' or omit)")
            return 1
        args.target = 'mp3'

    target_formats = ['mp3', 'm4a'] if args.target == 'both' else [args.target]

    # Source directory lookup tables
    _source_default = {
        'mp3': AUDIO_OUTPUT_DIR,
        'm4a': AUDIO_OUTPUT_DIR_M4A,
        'flac': AUDIO_OUTPUT_DIR_FLAC,
    }
    _source_subdir = {'mp3': 'MP3', 'm4a': 'M4A', 'flac': 'FLAC'}

    if args.top_level_directory:
        source_dir = args.top_level_directory / _source_subdir[args.source]
    else:
        source_dir = Path(_source_default[args.source])

    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist")
        return 1

    # Target directory lookup tables
    _target_default = {'mp3': AUDIO_OUTPUT_DIR, 'm4a': AUDIO_OUTPUT_DIR_M4A}
    _target_subdir = {'mp3': 'MP3', 'm4a': 'M4A'}

    target_dirs: list[Path] = []
    for fmt in target_formats:
        if args.top_level_directory:
            target_dirs.append(args.top_level_directory / _target_subdir[fmt])
        else:
            target_dirs.append(Path(_target_default[fmt]))

    for target_dir in target_dirs:
        if not target_dir.exists():
            print(f"Error: Target directory '{target_dir}' does not exist")
            return 1

    # Get source files (case-insensitive on all platforms)
    source_files = sorted(
        f for f in source_dir.iterdir()
        if f.suffix.lower() == f'.{args.source}'
    )
    if not source_files:
        print(f'No {args.source.upper()} files found in {source_dir}')
        return 0

    processed_count = 0
    warning_count = 0
    converted_count = 0

    for target_fmt, target_dir in zip(target_formats, target_dirs):
        fmt_label = f'{args.source.upper()} → {target_fmt.upper()}'
        print(f'Processing {fmt_label} ({len(source_files)} files)...')

        for source_file in source_files:
            print(f'  {source_file.name}')
            stem = source_file.stem
            if args.prefix and not stem.lower().startswith(f'{args.prefix.lower()} - '):
                stem = f'{args.prefix} - {stem}'
            target_file = target_dir / (stem + f'.{target_fmt}')
            processed, warned, converted = _process_file(
                source_file=source_file,
                target_file=target_file,
                source_format=args.source,
                target_format=target_fmt,
                create_missing_files=args.create_missing_files,
            )
            if processed:
                processed_count += 1
            if warned:
                warning_count += 1
            if converted:
                converted_count += 1

    print(
        f'\nCompleted: {processed_count} files processed, '
        f'{converted_count} files converted, {warning_count} warnings'
    )

    # Return 1 if there were warnings (missing files, conversion failures, etc.)
    return 1 if warning_count > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
