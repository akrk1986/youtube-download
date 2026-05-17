#!/usr/bin/env python3
"""
Dump the actual raw bytes of ID3 text frames to diagnose encoding issues.
This shows the exact byte sequence including BOM markers.
"""
import sys
from pathlib import Path

sys.path.append('..')

from mutagen.id3 import ID3


def dump_frame_bytes(file_path: Path, frame_id: str = 'TIT2') -> None:
    """
    Display the raw byte content of a specific ID3 frame.

    Args:
        file_path: Path to the MP3 file
        frame_id: Frame ID to dump (default: TIT2 for title)
    """
    try:
        id3 = ID3(file_path)

        print(f'\nFile: {file_path.name}')
        print(f'Frame: {frame_id}')
        print('=' * 80)

        if frame_id not in id3:
            print(f'Frame {frame_id} not found in file')
            return

        frame = id3[frame_id]

        # Get the text value for display
        if hasattr(frame, 'text') and frame.text:
            text_value = str(frame.text[0])
            print(f'Text value: {text_value}')
            print()

        # Get encoding
        if hasattr(frame, 'encoding'):
            encoding_names = {
                0: 'Latin-1',
                1: 'UTF-16 with BOM',
                2: 'UTF-16BE (no BOM)',
                3: 'UTF-8'
            }
            print(f'Encoding flag: {frame.encoding} ({encoding_names.get(frame.encoding, "Unknown")})')
            print()

        # Get the raw bytes
        # The frame data includes: [encoding byte][text bytes including BOM if UTF-16]
        frame_data = frame._writeData()

        print('Raw frame bytes (first 100 bytes):')
        print('Byte offset | Hex values                                        | ASCII')
        print('-' * 80)

        for i in range(0, min(len(frame_data), 100), 16):
            chunk = frame_data[i:i+16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f'{i:04x}       | {hex_str:<48} | {ascii_str}')

        print()
        print(f'Total frame size: {len(frame_data)} bytes')

        # Analyze the BOM if present
        if len(frame_data) > 3 and frame_data[0] == 1:  # encoding=1 (UTF-16)
            bom = frame_data[1:3]
            print()
            print('BOM Analysis:')
            if bom == b'\xff\xfe':
                print('  BOM: FF FE (UTF-16 Little-Endian) ✓ Correct for most systems')
            elif bom == b'\xfe\xff':
                print('  BOM: FE FF (UTF-16 Big-Endian) ⚠ May cause issues on Android')
            else:
                print(f'  BOM: {bom[0]:02x} {bom[1]:02x} (Unexpected!)')

        print('=' * 80)

    except Exception as e:
        print(f'Error: {e}')


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print('Usage: python dump-mp3-bytes.py <mp3-file> [frame-id]')
        print()
        print('Dumps the raw byte content of an ID3 frame to diagnose encoding issues.')
        print('Default frame: TIT2 (title)')
        print('Other common frames: TPE1 (artist), TALB (album), TPE2 (album artist)')
        sys.exit(1)

    file_path = Path(sys.argv[1])
    frame_id = sys.argv[2] if len(sys.argv) > 2 else 'TIT2'

    if not file_path.exists():
        print(f'Error: File not found: {file_path}')
        sys.exit(1)

    dump_frame_bytes(file_path=file_path, frame_id=frame_id)


if __name__ == '__main__':
    main()
