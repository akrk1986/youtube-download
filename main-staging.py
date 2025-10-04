#!/usr/bin/env python3
"""
Main staging script for copying audio tags between MP3 and M4A files.
Accepts --source parameter to specify source audio format (mp3 or m4a).
"""

import argparse
import sys
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError, ID3, COMM
from mutagen.mp4 import MP4
import arrow
from funcs_audio_conversion import convert_mp3_to_m4a, convert_m4a_to_mp3


def normalize_year(year_str):
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
        elif len(year_str) == 4 and year_str.isdigit():
            # Already YYYY format
            return year_str
        else:
            # Try to parse as date
            parsed_date = arrow.get(year_str)
            return str(parsed_date.year)
    except:
        # Fallback to regex extraction
        import re
        match = re.search(r'\d{4}', year_str)
        if match:
            return match.group()

    return ''


def extract_mp3_tags(file_path):
    """Extract relevant tags from MP3 file using EasyID3 and ID3."""
    try:
        # Use EasyID3 for most tags
        audio = EasyID3(file_path)
        year = normalize_year(audio.get('date', [''])[0])

        # Use raw ID3 for comment tag
        id3_audio = ID3(file_path)
        comment = ''
        if 'COMM::eng' in id3_audio:
            comment = str(id3_audio['COMM::eng'].text[0])
        elif id3_audio.getall('COMM'):
            # Get first comment if no English comment found
            comment = str(id3_audio.getall('COMM')[0].text[0])

        return {
            'title': audio.get('title', [''])[0],
            'artist': audio.get('artist', [''])[0],
            'albumartist': audio.get('albumartist', [''])[0],
            'date': year,
            'album': audio.get('album', [''])[0],
            'tracknumber': audio.get('tracknumber', [''])[0],
            'comment': comment,
            'composer': audio.get('composer', [''])[0]
        }
    except (ID3NoHeaderError, Exception) as e:
        print(f'Error reading MP3 tags from {file_path}: {e}')
        return None


def extract_m4a_tags(file_path):
    """Extract relevant tags from M4A file using MP4."""
    try:
        audio = MP4(file_path)
        year = normalize_year(audio.get('\xa9day', [''])[0] if audio.get('\xa9day') else '')
        return {
            'title': audio.get('\xa9nam', [''])[0] if audio.get('\xa9nam') else '',
            'artist': audio.get('\xa9ART', [''])[0] if audio.get('\xa9ART') else '',
            'albumartist': audio.get('aART', [''])[0] if audio.get('aART') else '',
            'date': year,
            'album': audio.get('\xa9alb', [''])[0] if audio.get('\xa9alb') else '',
            'tracknumber': str(audio.get('trkn', [(0, 0)])[0][0]) if audio.get('trkn') and audio.get('trkn')[0][0] > 0 else '',
            'comment': audio.get('\xa9cmt', [''])[0] if audio.get('\xa9cmt') else '',
            'composer': audio.get('\xa9wrt', [''])[0] if audio.get('\xa9wrt') else ''
        }
    except Exception as e:
        print(f'Error reading M4A tags from {file_path}: {e}')
        return None


def apply_mp3_tags(file_path, tags):
    """Apply tags to MP3 file using EasyID3 and ID3."""
    try:
        # Handle most tags with EasyID3
        try:
            audio = EasyID3(file_path)
        except ID3NoHeaderError:
            audio = EasyID3()

        # Handle comment separately with raw ID3
        id3_audio = ID3(file_path)

        written_tags = []
        comment_written = False

        for key, value in tags.items():
            if value:  # Only set non-empty values
                if key == 'comment':
                    # Set comment using raw ID3
                    id3_audio.add(COMM(encoding=3, lang='eng', desc='', text=[value]))
                    written_tags.append('comment')
                    comment_written = True
                else:
                    audio[key] = [value]
                    written_tags.append(key)

        audio.save(file_path)
        if comment_written:
            id3_audio.save(file_path)

        if written_tags:
            print(f'  Written tags: {", ".join(written_tags)}')

        return True
    except Exception as e:
        print(f'Error writing MP3 tags to {file_path}: {e}')
        return False


def apply_m4a_tags(file_path, tags):
    """Apply tags to M4A file using MP4."""
    try:
        audio = MP4(file_path)

        # Map common tag names to M4A atom names
        tag_mapping = {
            'title': '\xa9nam',
            'artist': '\xa9ART',
            'albumartist': 'aART',
            'date': '\xa9day',
            'album': '\xa9alb',
            'comment': '\xa9cmt',
            'composer': '\xa9wrt'
        }

        written_tags = []

        for key, value in tags.items():
            if value:  # Only set non-empty values
                if key == 'tracknumber':
                    try:
                        track_num = int(value)
                        audio['trkn'] = [(track_num, 0)]
                        written_tags.append('tracknumber')
                    except ValueError:
                        pass
                elif key in tag_mapping:
                    audio[tag_mapping[key]] = [value]
                    written_tags.append(key)

        audio.save(file_path)

        if written_tags:
            print(f'  Written tags: {", ".join(written_tags)}')

        return True
    except Exception as e:
        print(f'Error writing M4A tags to {file_path}: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Copy audio tags between MP3 and M4A staging directories')
    parser.add_argument(
        '--source',
        required=True,
        choices=['mp3', 'm4a'],
        help='Source audio format to read tags from (mp3 or m4a)'
    )
    parser.add_argument(
        '--create-missing-files',
        action='store_true',
        help='Convert and create missing target files using ffmpeg before copying tags'
    )
    parser.add_argument(
        '--top-level-directory',
        type=lambda p: Path(p) if Path(p).exists() and Path(p).is_dir() else parser.error(f"Directory '{p}' does not exist"),
        help='Top-level directory containing MP3 and M4A subfolders'
    )

    args = parser.parse_args()

    # Define directories
    if args.top_level_directory:
        top_dir = args.top_level_directory
        source_dir = top_dir / args.source.upper()
        target_format = 'm4a' if args.source == 'mp3' else 'mp3'
        target_dir = top_dir / target_format.upper()
    else:
        source_dir = Path(f'staging-{args.source}')
        target_format = 'm4a' if args.source == 'mp3' else 'mp3'
        target_dir = Path(f'staging-{target_format}')

    # Check if directories exist
    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist")
        sys.exit(1)

    if not target_dir.exists():
        print(f"Error: Target directory '{target_dir}' does not exist")
        sys.exit(1)

    print(f'Copying tags from {args.source.upper()} files to {target_format.upper()} files...')

    # Get source files
    source_files = list(source_dir.glob(f'*.{args.source}'))
    if not source_files:
        print(f'No {args.source.upper()} files found in {source_dir}')
        return

    processed_count = 0
    warning_count = 0
    converted_count = 0

    for source_file in source_files:
        print(f'Processing: {source_file.name}')

        # Generate target file path with different extension
        target_file = target_dir / (source_file.stem + f'.{target_format}')

        # Check if target file exists and is not empty
        if not target_file.exists() or target_file.stat().st_size == 0:
            if args.create_missing_files:
                print(f"  Target file '{target_file.name}' does not exist or is empty, converting...")
                # Convert source file to target format
                if args.source == 'mp3':
                    result = convert_mp3_to_m4a(source_file, target_file)
                else:
                    result = convert_m4a_to_mp3(source_file, target_file)

                if result is None:
                    print(f'  Failed to convert {source_file.name}')
                    warning_count += 1
                    continue
                converted_count += 1
            else:
                print(f"  WARNING: Target file '{target_file.name}' not found")
                warning_count += 1
                continue

        # Extract tags from source file
        if args.source == 'mp3':
            tags = extract_mp3_tags(source_file)
        else:
            tags = extract_m4a_tags(source_file)

        if tags is None:
            continue

        # Apply tags to target file
        if target_format == 'mp3':
            success = apply_mp3_tags(target_file, tags)
        else:
            success = apply_m4a_tags(target_file, tags)

        if success:
            processed_count += 1

    print(f'\nCompleted: {processed_count} files processed, {converted_count} files converted, {warning_count} warnings')


if __name__ == '__main__':
    main()