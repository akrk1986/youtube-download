#!/usr/bin/env python3
"""
Fix MP3 encoding for existing files by forcing UTF-16 encoding on all text frames.
This fixes Turkish/Greek/Hebrew characters showing as Chinese/Japanese on mobile devices.
"""
import sys
import argparse
from pathlib import Path

sys.path.append('..')

from funcs_audio_tag_handlers import _force_utf16_encoding
from project_defs import GLOB_MP3_FILES, GLOB_MP3_FILES_UPPER
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


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
            _force_utf16_encoding(file_path=mp3_file)
            summary['fixed'] += 1
        except Exception as e:
            error_msg = f'Failed to fix {mp3_file.name}: {e}'
            summary['errors'].append(error_msg)
            logger.error(error_msg)

    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fix MP3 encoding for Turkish/Greek/Hebrew characters by forcing UTF-16 encoding on all text frames.'
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

    logger.info(f'Fixing MP3 encoding in folder: {args.folder}')
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
