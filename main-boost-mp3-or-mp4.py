#!/usr/bin/env python3
"""A main script to boost volume of MP4/MP3 files using ffmpeg loudnorm filter."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import shared utilities
# sys.path.insert(0, str(Path(__file__).parent.parent))
from funcs_for_main_yt_dlp import get_ffmpeg_path


FFMPEG_EXE = get_ffmpeg_path()
TARGET_PEAK_DB = -0.5  # Target peak level (with safety margin to avoid clipping)


def detect_audio_levels(input_file: Path) -> tuple[float, float]:
    """
    Detect audio levels using ffmpeg volumedetect filter.

    Args:
        input_file: Path to the input audio/video file.

    Returns:
        tuple: (mean_volume_db, max_volume_db)

    Raises:
        RuntimeError: If unable to detect audio levels.
    """
    cmd = [
        FFMPEG_EXE,
        '-i', str(input_file),
        '-af', 'volumedetect',
        '-f', 'null',
        '/dev/null' if sys.platform != 'win32' else 'NUL'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        # Parse mean_volume and max_volume from output
        mean_match = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', output)
        max_match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', output)

        if not mean_match or not max_match:
            raise RuntimeError('Failed to parse volume information')

        mean_volume = float(mean_match.group(1))
        max_volume = float(max_match.group(1))

        return mean_volume, max_volume

    except Exception as e:
        raise RuntimeError(f'Error detecting audio levels: {e}')


def calculate_boost_value(max_volume_db: float, target_db: float = TARGET_PEAK_DB) -> float:
    """
    Calculate the boost value needed to reach target peak level.

    Args:
        max_volume_db: Current maximum volume in dB.
        target_db: Target peak level in dB (default: TARGET_PEAK_DB).

    Returns:
        float: Linear gain multiplier needed.
    """
    # Calculate the dB difference
    gain_db = target_db - max_volume_db

    # Convert dB to linear gain: gain = 10^(dB/20)
    linear_gain = 10 ** (gain_db / 20)

    return linear_gain


def boost_mp3_volume(input_file: Path, use_loudnorm: bool = False, boost_value: float = 3.0) -> Path:
    """
    Boost MP3 volume using ffmpeg loudnorm filter or volume multiplier.

    Args:
        input_file: Path to the input MP3 file.
        use_loudnorm: If True, use loudnorm filter. If False, use volume multiplier.
        boost_value: Volume multiplier value (only used when use_loudnorm is False).

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

    # Build audio filter based on mode
    if use_loudnorm:
        audio_filter = 'loudnorm=I=-16:TP=-1.5:LRA=11'
    else:
        audio_filter = f'volume={boost_value}'

    cmd = [
        FFMPEG_EXE,
        '-y',
        '-i', str(input_file),
        '-af', audio_filter,
        str(output_file)
    ]

    print(f'Running ffmpeg command: {cmd}')
    print(f'Input: {input_file}')
    print(f'Output: {output_file}')
    print(f'Mode: {"loudnorm" if use_loudnorm else f"volume boost ({boost_value}x)"}')

    try:
        subprocess.run(cmd, check=True)
        print(f'Successfully created {output_file}')
        return output_file
    except subprocess.CalledProcessError as e:
        print(f'Error running ffmpeg: {e}')
        raise


def boost_mp4_volume(input_file: Path, use_loudnorm: bool = False, boost_value: float = 3.0) -> Path:
    """
    Boost MP4 volume using ffmpeg loudnorm filter or volume multiplier.

    Args:
        input_file: Path to the input MP4 file.
        use_loudnorm: If True, use loudnorm filter. If False, use volume multiplier.
        boost_value: Volume multiplier value (only used when use_loudnorm is False).

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

    # Build audio filter based on mode
    if use_loudnorm:
        audio_filter = 'loudnorm=I=-16:TP=-1.5:LRA=11'
    else:
        audio_filter = f'volume={boost_value}'

    cmd = [
        FFMPEG_EXE,
        '-y',
        '-i', str(input_file),
        '-af', audio_filter,
        '-c:v', 'copy',
        str(output_file)
    ]

    print(f'Running ffmpeg command: {cmd}')
    print(f'Input: {input_file}')
    print(f'Output: {output_file}')
    print(f'Mode: {"loudnorm" if use_loudnorm else f"volume boost ({boost_value}x)"}')

    try:
        subprocess.run(cmd, check=True)
        print(f'Successfully created {output_file}')
        return output_file
    except subprocess.CalledProcessError as e:
        print(f'Error running ffmpeg: {e}')
        raise

def main() -> None:
    """Main function to boost volume of all MP3/MP4 files in a directory."""
    parser = argparse.ArgumentParser(
        description='Boost MP3/MP4 volume using ffmpeg loudnorm filter or volume multiplier')
    parser.add_argument('input_dir', type=Path,
                        help='Path to the directory containing MP3/MP4 files')

    # Create mutually exclusive group for boost method
    boost_group = parser.add_mutually_exclusive_group()
    boost_group.add_argument('--loudnorm', choices=['yes', 'no'],
                             help='Use loudnorm filter for volume normalization')
    boost_group.add_argument('--boost', type=float, nargs='?', const=3.0, default=3.0,
                             metavar='BOOST_VALUE',
                             help='Use volume multiplier (default: %(default)s)')

    args = parser.parse_args()

    # Validate directory exists
    if not args.input_dir.exists():
        print(f'Error: Directory does not exist: {args.input_dir}')
        sys.exit(1)

    if not args.input_dir.is_dir():
        print(f'Error: Path is not a directory: {args.input_dir}')
        sys.exit(1)

    # Determine mode
    use_loudnorm = args.loudnorm == 'yes'
    boost_value = args.boost if args.loudnorm is None else 3.0

    # Find all MP3/MP4/M4A files in directory (case-insensitive)
    # Exclude files already ending with '-boost'
    
    supported_extensions = {'.mp3', '.mp4', '.m4a'}
    audio_files = [
        f for f in args.input_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in supported_extensions
        and not f.stem.endswith('-boost')
    ]

    if not audio_files:
        print(f'Error: No MP3/MP4/M4A files found in directory: {args.input_dir}')
        sys.exit(1)

    # Sort files by name for consistent processing order
    audio_files.sort()

    # Process each file
    mp3_count = 0
    mp4_count = 0
    skipped_files = []
    failed_files = []

    print(f'Found {len(audio_files)} candidate file(s) to process')
    if use_loudnorm:
        print(f'Mode: loudnorm')
    else:
        print(f'Mode: auto-calculated volume boost (target: {TARGET_PEAK_DB} dB)')
    print('-' * 60)

    for audio_file in audio_files:
        file_extension = audio_file.suffix.lower()
        print(f'\nProcessing: {audio_file.name}')

        try:
            # If using manual boost value or loudnorm, skip level detection
            if use_loudnorm or args.loudnorm == 'no':
                # Use provided boost value
                actual_boost = boost_value
                print(f'  Using manual boost: {actual_boost:.2f}x')
            else:
                # Auto-detect levels and calculate boost
                print(f'  Detecting audio levels...')
                mean_vol, max_vol = detect_audio_levels(input_file=audio_file)
                print(f'  Current levels: mean={mean_vol:.1f} dB, max={max_vol:.1f} dB')

                # Check if boost is needed
                if max_vol >= TARGET_PEAK_DB:
                    print(f'  Already at target level ({max_vol:.1f} dB >= {TARGET_PEAK_DB} dB) - SKIPPING')
                    skipped_files.append(audio_file.name)
                    continue

                # Calculate needed boost
                actual_boost = calculate_boost_value(max_volume_db=max_vol, target_db=TARGET_PEAK_DB)
                gain_db = TARGET_PEAK_DB - max_vol
                print(f'  Calculated boost: {actual_boost:.2f}x (+{gain_db:.1f} dB)')

            # Apply boost
            if file_extension == '.mp3':
                boost_mp3_volume(
                    input_file=audio_file,
                    use_loudnorm=use_loudnorm,
                    boost_value=actual_boost
                )
                mp3_count += 1
            elif file_extension in ['.mp4', '.m4a']:
                boost_mp4_volume(
                    input_file=audio_file,
                    use_loudnorm=use_loudnorm,
                    boost_value=actual_boost
                )
                mp4_count += 1
        except Exception as e:
            print(f'Error processing {audio_file.name}: {e}')
            failed_files.append(audio_file.name)

    # Print summary
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'MP3 files boosted: {mp3_count}')
    print(f'MP4/M4A files boosted: {mp4_count}')
    print(f'Total files processed: {mp3_count + mp4_count}')

    if skipped_files:
        print(f'\nSkipped files (already at target level): {len(skipped_files)}')
        for skipped_file in skipped_files:
            print(f'  - {skipped_file}')

    if failed_files:
        print(f'\nFailed files ({len(failed_files)}):')
        for failed_file in failed_files:
            print(f'  - {failed_file}')
        sys.exit(1)

if __name__ == '__main__':
    main()
