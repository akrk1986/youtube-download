#!/usr/bin/env python3
"""
Test script for YouTube downloader functions
"""

import argparse
from pathlib import Path
import sys
import logging
from Beta.yt_dlp_funcs import download_youtube_content, get_video_info, list_available_formats

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download YouTube videos and audio using yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://www.youtube.com/watch?v=VIDEO_ID
  %(prog)s https://www.youtube.com/playlist?list=PLAYLIST_ID --only-audio
  %(prog)s https://www.youtube.com/watch?v=VIDEO_ID --with-audio
  %(prog)s https://www.youtube.com/watch?v=VIDEO_ID --output-dir /path/to/downloads
        """
    )

    parser.add_argument(
        'url',
        help='YouTube URL (video or playlist)'
    )

    parser.add_argument(
        '--only-audio',
        action='store_true',
        help='Download only audio files (MP3 format)'
    )

    parser.add_argument(
        '--with-audio',
        action='store_true',
        help='Download both video (MP4) and audio (MP3) files'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path.cwd(),
        help='Output parent directory for downloads (default: current directory)'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Show video information without downloading'
    )

    parser.add_argument(
        '--list-formats',
        action='store_true',
        help='List available formats for the video'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def _setup_logging(verbose: bool) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)

    # Set yt-dlp logger level
    logging.getLogger('yt_dlp').setLevel(level)


def _validate_url(url: str) -> bool:
    """Validate YouTube URL"""
    youtube_domains = [
        'youtube.com',
        'www.youtube.com',
        'youtu.be',
        'm.youtube.com',
        'music.youtube.com'
    ]
    return any(domain in url for domain in youtube_domains)


def _print_video_info(info: dict) -> None:
    """Print video information in a formatted way"""
    if 'entries' in info:
        print(f"Playlist: {info.get('title', 'Unknown')}")
        print(f"Number of videos: {len(info['entries'])}")
        print(f"Uploader: {info.get('uploader', 'Unknown')}")
        print("\nVideos in playlist:")
        for i, entry in enumerate(info['entries'][:5], 1):  # Show first 5
            print(f"  {i}. {entry.get('title', 'Unknown title')}")
        if len(info['entries']) > 5:
            print(f"  ... and {len(info['entries']) - 5} more")
    else:
        print(f"Title: {info.get('title', 'Unknown')}")
        print(f"Uploader: {info.get('uploader', 'Unknown')}")
        print(f"Duration: {info.get('duration_string', 'Unknown')}")
        print(f"View count: {info.get('view_count', 'Unknown')}")
        print(f"Upload date: {info.get('upload_date', 'Unknown')}")


def _print_formats(formats: list) -> None:
    """Print available formats"""
    if not formats:
        print("No formats available")
        return

    print("\nAvailable formats:")
    print("Format ID | Extension | Resolution | Note")
    print("-" * 50)

    for fmt in formats:
        format_id = fmt.get('format_id', 'N/A')
        ext = fmt.get('ext', 'N/A')
        resolution = fmt.get('resolution', 'N/A')
        note = fmt.get('format_note', 'N/A')
        print(f"{format_id:9} | {ext:9} | {resolution:10} | {note}")


def _main() -> int:
    """Main function"""
    args = _parse_arguments()

    # Setup logging
    _setup_logging(args.verbose)

    # Validate URL
    if not _validate_url(args.url):
        logger.error("Invalid YouTube URL provided")
        return 1

    # Check for conflicting flags
    if args.only_audio and args.with_audio:
        logger.error("Cannot use --only-audio and --with-audio together")
        return 1

    try:
        # Handle info request
        if args.info:
            logger.info("Extracting video information...")
            info = get_video_info(args.url)
            if info:
                _print_video_info(info)
            else:
                logger.error("Failed to extract video information")
                return 1
            return 0

        # Handle format listing
        if args.list_formats:
            logger.info("Listing available formats...")
            formats = list_available_formats(args.url)
            _print_formats(formats)
            return 0

        # Validate output directory
        if not args.output_dir.exists():
            logger.info(f"Creating output directory: {args.output_dir}")
            args.output_dir.mkdir(parents=True, exist_ok=True)

        # Download content
        logger.info(f"Starting download from: {args.url}")
        logger.info(f"Output directory: {args.output_dir}")

        success = download_youtube_content(
            url=args.url,
            output_dir=args.output_dir,
            only_audio=args.only_audio,
            with_audio=args.with_audio
        )

        if success:
            logger.info("Download completed successfully!")
            return 0
        else:
            logger.error("Download failed")
            return 1

    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(_main())
