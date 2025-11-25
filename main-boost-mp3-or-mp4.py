#!/usr/bin/env python3
"""A main script to boost volume of MP4/MP3 files using ffmpeg loudnorm filter."""
import argparse
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import shared utilities
# sys.path.insert(0, str(Path(__file__).parent.parent))
from funcs_for_main_yt_dlp import get_ffmpeg_path


FFMPEG_EXE = get_ffmpeg_path()

def boost_mp4_volume(input_file: Path) -> Path:
    """
    Boost MP4 volume using ffmpeg loudnorm filter.

    Args:
        input_file: Path to the input MP4 file.

    Returns:
        Path: Path to the output file with boosted volume.

    Raises:
        subprocess.CalledProcessError: If ffmpeg command fails.
        FileNotFoundError: If input file does not exist.
    """
    if not input_file.exists():
        raise FileNotFoundError(f'Input file {input_file!r} does not exist')

    # Create output filename with '-boost' suffix
    output_file = input_file.parent / f'{input_file.stem}-boost{input_file.suffix}'

    cmd = [
        FFMPEG_EXE,
        '-y',
        '-i', str(input_file),
        '-af', 'volume=3.0',
        '-c:v', 'copy',
        str(output_file)
    ]

    print(f'Running ffmpeg command: {cmd}')
    print(f'Input: {input_file}')
    print(f'Output: {output_file}')

    try:
        subprocess.run(cmd, check=True)
        print(f'Successfully created {output_file}')
        return output_file
    except subprocess.CalledProcessError as e:
        print(f'Error running ffmpeg: {e}')
        raise

def main() -> None:
    """Main function to test MP4 volume boost."""
    parser = argparse.ArgumentParser(
        description='Boost MP3/MP4 volume using ffmpeg loudnorm filter')
    parser.add_argument('input_file', type=Path,
                        help='Path to the input MP3/MP4 file')
    args = parser.parse_args()

    try:
        output_file = boost_mp4_volume(input_file=args.input_file)
        print(f'\nVolume boost complete!')
        print(f'Output file: {output_file}')
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
