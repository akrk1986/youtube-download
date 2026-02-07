#!/usr/bin/env python3
"""
Check the actual encoding used in MP3 ID3 tags.
This helps diagnose encoding issues with Turkish/Greek/Hebrew characters.
"""
import sys
from pathlib import Path

sys.path.append('..')

from mutagen.id3 import ID3


def check_mp3_encoding(file_path: Path) -> None:
    """
    Display the encoding used for each text frame in an MP3 file.

    Args:
        file_path: Path to the MP3 file to check
    """
    try:
        id3 = ID3(file_path)

        print(f'\nFile: {file_path.name}')
        print('=' * 80)

        # ID3 version
        print(f'ID3 version: {id3.version}')
        print()

        # Encoding names
        encoding_names = {
            0: 'Latin-1 (ISO-8859-1)',
            1: 'UTF-16 with BOM',
            2: 'UTF-16BE (Big Endian, no BOM)',
            3: 'UTF-8'
        }

        # Check common text frames
        text_frames = ['TIT2', 'TPE1', 'TPE2', 'TALB', 'TDRC', 'TRCK', 'TENC']

        found_frames = False
        for frame_id in text_frames:
            if frame_id in id3:
                frame = id3[frame_id]
                if hasattr(frame, 'encoding'):
                    encoding = frame.encoding
                    encoding_name = encoding_names.get(encoding, f'Unknown ({encoding})')

                    # Get the text value
                    if hasattr(frame, 'text'):
                        text_value = str(frame.text[0]) if frame.text else '(empty)'
                    else:
                        text_value = str(frame)

                    # Truncate long values
                    if len(text_value) > 50:
                        text_value = text_value[:47] + '...'

                    print(f'{frame_id:8} | Encoding: {encoding} ({encoding_name:30}) | Value: {text_value}')
                    found_frames = True

        if not found_frames:
            print('No text frames found in file')

        print('=' * 80)

    except Exception as e:
        print(f'Error reading file: {e}')


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print('Usage: python check-mp3-encoding.py <mp3-file>')
        print()
        print('This script displays the encoding used for each text frame in an MP3 file.')
        print('Encoding values:')
        print('  0 = Latin-1 (ISO-8859-1) - Limited character support')
        print('  1 = UTF-16 with BOM - Best mobile compatibility')
        print('  2 = UTF-16BE (Big Endian, no BOM) - May have compatibility issues')
        print('  3 = UTF-8 - Poor mobile device support (ID3v2.4 only)')
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f'Error: File not found: {file_path}')
        sys.exit(1)

    if not file_path.suffix.lower() == '.mp3':
        print(f'Warning: File does not have .mp3 extension: {file_path}')

    check_mp3_encoding(file_path=file_path)


if __name__ == '__main__':
    main()
