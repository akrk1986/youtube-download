"""
Test script for URL extraction from text and ODF files.
"""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_url_extraction import print_urls_from_file
import argparse


def main():
    """Main entry point for URL extraction test."""
    parser = argparse.ArgumentParser(
        description='Extract and print URLs from text or ODF files'
    )
    parser.add_argument(
        'file_path',
        type=Path,
        help='Path to the text (.txt) or ODF (.odt) file'
    )

    args = parser.parse_args()

    # Convert Path to string for the function
    print_urls_from_file(file_path=str(args.file_path))


if __name__ == '__main__':
    main()
