#!/usr/bin/env python3
"""
Main script to extract YouTube video chapters using yt-dlp.
"""

import argparse
import sys
from pathlib import Path
from funcs_video_info.chapter_extraction import extract_youtube_chapters


def main() -> None:
    """Main function to handle command line arguments and extract chapters."""
    parser = argparse.ArgumentParser(
        description="Extract chapters from YouTube videos and save to CSV"
    )
    parser.add_argument(
        'url',
        nargs='?',
        help='YouTube video URL'
    )
    parser.add_argument(
        '--yt-dlp-path',
        type=Path,
        default=Path('yt-dlp'),
        help='Path to yt-dlp executable (default: yt-dlp)'
    )

    args = parser.parse_args()

    # Get URL from command line or prompt user
    url = args.url
    if not url:
        try:
            url = input("Enter YouTube video URL: ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(1)

    if not url:
        print("Error: No URL provided.")
        sys.exit(1)

    # Validate yt-dlp path
    yt_dlp_path = args.yt_dlp_path
    if not yt_dlp_path.exists() and yt_dlp_path.name == 'yt-dlp':
        # Try common alternative paths
        alternatives = [
            Path('yt-dlp.exe'),  # Windows
            Path('/usr/local/bin/yt-dlp'),  # Common install location
            Path('/usr/bin/yt-dlp'),  # System install
        ]

        for alt_path in alternatives:
            if alt_path.exists():
                yt_dlp_path = alt_path
                break
        else:
            print("Error: yt-dlp executable not found.")
            print("Please install yt-dlp or specify the correct path with --yt-dlp-path")
            sys.exit(1)

    try:
        csv_file = extract_youtube_chapters(yt_dlp_path, url)
        if csv_file:
            print(f"Success! Chapters saved to: {csv_file}")
        else:
            print("No chapters found in the video.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
