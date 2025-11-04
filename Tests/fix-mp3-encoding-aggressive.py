#!/usr/bin/env python3
"""
Aggressively fix MP3 encoding by completely re-writing text frames with UTF-16LE.
This fixes Turkish/Greek/Hebrew characters that show as Chinese/Japanese on mobile devices.
"""
import sys
import argparse
from pathlib import Path

sys.path.append('..')

from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, COMM
from project_defs import GLOB_MP3_FILES, GLOB_MP3_FILES_UPPER
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def aggressive_fix_encoding(file_path: Path) -> bool:
    """
    Aggressively fix encoding by reading text and completely re-writing frames.

    This is more thorough than just changing the encoding flag - it actually
    re-creates the frames with proper UTF-16LE encoding.

    Args:
        file_path: Path to the MP3 file to fix

    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        id3 = ID3(file_path)

        # Store original values
        original_values = {}

        # Frame mappings
        frame_map = {
            'TIT2': TIT2,
            'TPE1': TPE1,
            'TPE2': TPE2,
            'TALB': TALB,
            'TDRC': TDRC,
            'TRCK': TRCK
        }

        modified = False

        # Read existing values
        for frame_id, frame_class in frame_map.items():
            if frame_id in id3:
                frame = id3[frame_id]
                if hasattr(frame, 'text') and frame.text:
                    # Get the text value
                    text_value = str(frame.text[0])
                    original_values[frame_id] = text_value

                    # Delete the old frame
                    del id3[frame_id]

                    # Create new frame with explicit UTF-16 encoding (encoding=1)
                    new_frame = frame_class(encoding=1, text=text_value)
                    id3.add(new_frame)

                    modified = True
                    logger.debug(f'Re-created {frame_id} with UTF-16LE: {text_value[:50]}')

        if modified:
            # Save with ID3v2.3
            id3.save(file_path, v2_version=3)
            logger.info(f'Successfully fixed: {file_path.name}')
            return True
        else:
            logger.debug(f'No changes needed: {file_path.name}')
            return False

    except ID3NoHeaderError:
        logger.warning(f'No ID3 tags found: {file_path.name}')
        return False
    except Exception as e:
        logger.error(f'Failed to fix {file_path.name}: {e}')
        return False


def fix_mp3_files_in_folder(folder_path: Path, recursive: bool = False) -> dict:
    """
    Fix encoding for all MP3 files in the specified folder.

    Args:
        folder_path: Path to folder containing MP3 files
        recursive: If True, process subdirectories recursively

    Returns:
        dict: Summary with fixed_files count and any errors
    """
    summary = {'fixed': 0, 'skipped': 0, 'errors': []}

    if recursive:
        mp3_files = list(folder_path.rglob(GLOB_MP3_FILES)) + list(folder_path.rglob(GLOB_MP3_FILES_UPPER))
    else:
        mp3_files = list(folder_path.glob(GLOB_MP3_FILES)) + list(folder_path.glob(GLOB_MP3_FILES_UPPER))

    if not mp3_files:
        logger.warning(f'No MP3 files found in {folder_path}')
        return summary

    logger.info(f'Found {len(mp3_files)} MP3 files to process')

    for mp3_file in mp3_files:
        try:
            logger.info(f'Processing: {mp3_file.name}')
            if aggressive_fix_encoding(file_path=mp3_file):
                summary['fixed'] += 1
            else:
                summary['skipped'] += 1
        except Exception as e:
            error_msg = f'Failed to fix {mp3_file.name}: {e}'
            summary['errors'].append(error_msg)
            logger.error(error_msg)

    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Aggressively fix MP3 encoding by completely re-writing text frames with UTF-16LE.'
    )
    parser.add_argument(
        'folder',
        type=Path,
        help='Path to folder containing MP3 files to fix'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Process subdirectories recursively'
    )

    args = parser.parse_args()

    if not args.folder.exists():
        logger.error(f'Folder does not exist: {args.folder}')
        sys.exit(1)

    if not args.folder.is_dir():
        logger.error(f'Not a directory: {args.folder}')
        sys.exit(1)

    logger.info(f'Aggressively fixing MP3 encoding in folder: {args.folder}')
    if args.recursive:
        logger.info('Recursive mode enabled')

    summary = fix_mp3_files_in_folder(folder_path=args.folder, recursive=args.recursive)

    # Print summary
    logger.info('=' * 60)
    logger.info('Summary:')
    logger.info(f'Files fixed: {summary["fixed"]}')
    logger.info(f'Files skipped: {summary["skipped"]}')
    if summary['errors']:
        logger.warning(f'Errors: {len(summary["errors"])}')
        for error in summary['errors']:
            logger.warning(f'  - {error}')
    logger.info('=' * 60)


if __name__ == '__main__':
    main()
