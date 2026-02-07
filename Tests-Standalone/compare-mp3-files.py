#!/usr/bin/env python3
"""
Compare two MP3 files to find ALL differences in their ID3 tags.
This helps identify why identical text encoding shows differently on devices.
"""
import sys
from pathlib import Path

sys.path.append('..')

from mutagen.id3 import ID3
from mutagen.mp3 import MP3


def analyze_mp3_file(file_path: Path) -> dict:
    """
    Get complete information about an MP3 file's tags and structure.

    Args:
        file_path: Path to MP3 file

    Returns:
        dict: Complete file information
    """
    info = {
        'file_name': file_path.name,
        'file_size': file_path.stat().st_size,
        'frames': {},
        'frame_order': [],
        'id3_version': None,
        'audio_info': {}
    }

    try:
        # Load ID3 tags
        id3 = ID3(file_path)
        info['id3_version'] = id3.version

        # Get all frames
        for frame_id in id3.keys():
            frame = id3[frame_id]
            frame_info = {
                'frame_id': frame_id,
                'size': len(frame._writeData()) if hasattr(frame, '_writeData') else 0
            }

            # Get encoding if available
            if hasattr(frame, 'encoding'):
                frame_info['encoding'] = str(frame.encoding)

            # Get text if available
            if hasattr(frame, 'text'):
                frame_info['text'] = str(frame.text)
            elif hasattr(frame, 'data'):
                frame_info['has_data'] = True
                frame_info['data_size'] = len(frame.data)

            info['frames'][frame_id] = frame_info
            info['frame_order'].append(frame_id)

        # Get audio info
        mp3 = MP3(file_path)
        info['audio_info'] = {
            'length': mp3.info.length,
            'bitrate': mp3.info.bitrate,
            'sample_rate': mp3.info.sample_rate,
            'channels': mp3.info.channels
        }

    except Exception as e:
        info['error'] = str(e)

    return info


def compare_files(file1_path: Path, file2_path: Path) -> None:
    """
    Compare two MP3 files and show all differences.

    Args:
        file1_path: First MP3 file
        file2_path: Second MP3 file
    """
    print('Comparing MP3 Files')
    print('=' * 80)
    print(f'File 1: {file1_path.name}')
    print(f'File 2: {file2_path.name}')
    print('=' * 80)
    print()

    info1 = analyze_mp3_file(file_path=file1_path)
    info2 = analyze_mp3_file(file_path=file2_path)

    # Compare file sizes
    print('FILE SIZES:')
    print(f'  File 1: {info1["file_size"]:,} bytes')
    print(f'  File 2: {info2["file_size"]:,} bytes')
    if info1['file_size'] != info2['file_size']:
        print(f'  ⚠ DIFFERENT! Difference: {abs(info1["file_size"] - info2["file_size"]):,} bytes')
    print()

    # Compare ID3 versions
    print('ID3 VERSIONS:')
    print(f'  File 1: {info1["id3_version"]}')
    print(f'  File 2: {info2["id3_version"]}')
    if info1['id3_version'] != info2['id3_version']:
        print('  ⚠ DIFFERENT!')
    print()

    # Compare frames present
    frames1 = set(info1['frames'].keys())
    frames2 = set(info2['frames'].keys())

    print('FRAMES PRESENT:')
    print(f'  File 1: {len(frames1)} frames: {", ".join(sorted(frames1))}')
    print(f'  File 2: {len(frames2)} frames: {", ".join(sorted(frames2))}')

    only_in_1 = frames1 - frames2
    only_in_2 = frames2 - frames1

    if only_in_1:
        print(f'  ⚠ Only in File 1: {", ".join(sorted(only_in_1))}')
    if only_in_2:
        print(f'  ⚠ Only in File 2: {", ".join(sorted(only_in_2))}')
    print()

    # Compare frame order
    print('FRAME ORDER:')
    if info1['frame_order'] != info2['frame_order']:
        print('  ⚠ Frame order is DIFFERENT!')
        print(f'  File 1: {" → ".join(info1["frame_order"])}')
        print(f'  File 2: {" → ".join(info2["frame_order"])}')
    else:
        print('  ✓ Frame order is identical')
    print()

    # Compare common frames in detail
    common_frames = frames1 & frames2
    if common_frames:
        print('COMMON FRAMES COMPARISON:')
        for frame_id in sorted(common_frames):
            frame1 = info1['frames'][frame_id]
            frame2 = info2['frames'][frame_id]

            differences = []

            if frame1.get('encoding') != frame2.get('encoding'):
                differences.append(f"encoding: {frame1.get('encoding')} vs {frame2.get('encoding')}")

            if frame1.get('size') != frame2.get('size'):
                differences.append(f"size: {frame1.get('size')} vs {frame2.get('size')} bytes")

            if frame1.get('text') != frame2.get('text'):
                text1 = frame1.get('text', '')
                text2 = frame2.get('text', '')
                if len(text1) > 40:
                    text1 = text1[:37] + '...'
                if len(text2) > 40:
                    text2 = text2[:37] + '...'
                differences.append(f'text: "{text1}" vs "{text2}"')

            if differences:
                print(f'  {frame_id}: ⚠ {" | ".join(differences)}')
            else:
                print(f'  {frame_id}: ✓ Identical')
        print()

    # Compare audio properties
    print('AUDIO PROPERTIES:')
    audio1 = info1['audio_info']
    audio2 = info2['audio_info']
    for key in ['length', 'bitrate', 'sample_rate', 'channels']:
        if key in audio1 and key in audio2:
            if audio1[key] != audio2[key]:
                print(f'  {key}: {audio1[key]} vs {audio2[key]} ⚠ DIFFERENT!')
            else:
                print(f'  {key}: {audio1[key]} ✓')

    print('=' * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print('Usage: python compare-mp3-files.py <file1.mp3> <file2.mp3>')
        print()
        print('Compare two MP3 files to find all differences in ID3 tags and structure.')
        sys.exit(1)

    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])

    if not file1.exists():
        print(f'Error: File not found: {file1}')
        sys.exit(1)

    if not file2.exists():
        print(f'Error: File not found: {file2}')
        sys.exit(1)

    compare_files(file1_path=file1, file2_path=file2)


if __name__ == '__main__':
    main()
