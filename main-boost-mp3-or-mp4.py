#!/usr/bin/env python3
"""A main script to boost volume of MP4/MP3 files using ffmpeg loudnorm filter."""
import argparse
import sys
from pathlib import Path

from funcs_audio_boost import (
    MP3Booster,
    MP4Booster,
    TARGET_PEAK_DB,
    calculate_boost_value,
    detect_audio_levels,
)


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
    media_files = [
        f for f in args.input_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in supported_extensions
        and not f.stem.endswith('-boost')
    ]

    if not media_files:
        print(f'Error: No media (MP3/MP4/M4A) files found in directory: {args.input_dir}')
        sys.exit(1)

    # Sort files by name for consistent processing order
    media_files.sort()

    # Process each file
    mp3_count = 0
    mp4_count = 0
    skipped_files = []
    failed_files = []

    print(f'Found {len(media_files)} candidate file(s) to process')
    if use_loudnorm:
        print(f'Mode: loudnorm')
    else:
        print(f'Mode: auto-calculated volume boost (target: {TARGET_PEAK_DB} dB)')
    print('-' * 60)

    for media_file in media_files:
        file_extension = media_file.suffix.lower()
        print(f'\nProcessing: {media_file.name}')

        try:
            # If using manual boost value or loudnorm, skip level detection
            if use_loudnorm or args.loudnorm == 'no':
                # Use provided boost value
                actual_boost = boost_value
                print(f'  Using manual boost: {actual_boost:.2f}x')
            else:
                # Auto-detect levels and calculate boost
                print(f'  Detecting audio levels...')
                mean_vol, max_vol = detect_audio_levels(input_file=media_file)
                print(f'  Current levels: mean={mean_vol:.1f} dB, max={max_vol:.1f} dB')

                # Check if boost is needed
                if max_vol >= TARGET_PEAK_DB:
                    print(f'  Already at target level ({max_vol:.1f} dB >= {TARGET_PEAK_DB} dB) - SKIPPING')
                    skipped_files.append(media_file.name)
                    continue

                # Calculate needed boost
                actual_boost = calculate_boost_value(max_volume_db=max_vol, target_db=TARGET_PEAK_DB)
                gain_db = TARGET_PEAK_DB - max_vol
                print(f'  Calculated boost: {actual_boost:.2f}x (+{gain_db:.1f} dB)')

            # Apply boost using appropriate booster class
            if file_extension == '.mp3':
                booster = MP3Booster()
                booster.boost_volume(
                    input_file=media_file,
                    use_loudnorm=use_loudnorm,
                    boost_value=actual_boost
                )
                mp3_count += 1
            elif file_extension in ['.mp4', '.m4a']:
                booster = MP4Booster()
                booster.boost_volume(
                    input_file=media_file,
                    use_loudnorm=use_loudnorm,
                    boost_value=actual_boost
                )
                mp4_count += 1
        except Exception as e:
            print(f'Error processing {media_file.name}: {e}')
            failed_files.append(media_file.name)

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
