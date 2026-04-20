"""Utility functions for main script."""
import argparse
import logging
import socket
import sys

import arrow

from project_defs import DEFAULT_AUDIO_FORMAT, VALID_AUDIO_FORMATS

logger = logging.getLogger(__name__)


def format_elapsed_time(seconds: float) -> str:
    """Format elapsed time in seconds to a human-readable string."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f'{hours}h {minutes}m {secs}s'
    if minutes > 0:
        return f'{minutes}m {secs}s'
    return f'{secs}s'


def generate_session_id() -> str:
    """Generate a unique session identifier with timestamp and hostname."""
    hostname = socket.gethostname()
    timestamp = arrow.now().format('YYYY-MM-DD HH:mm')
    return f'[{timestamp} {hostname}]'


def parse_arguments(argv: list[str] | None = None, version: str = '') -> argparse.Namespace:
    """Parse and return command-line arguments.

    Args:
        version: Version string shown by --version.
        argv: Command-line arguments to parse. If None, uses sys.argv.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description='Download YouTube playlist/video, optionally with subtitles.')
    parser.add_argument('video_url', nargs='?', help='Playlist/video URL')
    parser.add_argument('--audio-format', default=DEFAULT_AUDIO_FORMAT,
                        help='Audio format for extraction: mp3, m4a, flac, or comma-separated list '
                             '(e.g., mp3,m4a). (default: %(default)s)')
    parser.add_argument('--split-chapters', action='store_true', help='Split to chapters')
    parser.add_argument('--video-download-timeout', type=int,
                        help='Timeout in seconds for video downloads. If specified, applies to all sites. '
                             'If not specified, uses defaults: 300s for YouTube/Facebook, 3600s for other sites')
    parser.add_argument('--subs', action='store_true', help='Download subtitles')
    parser.add_argument('--json', action='store_true', help='Write JSON file')
    parser.add_argument('--no-log-file', action='store_true', help='Disable logging to file')
    parser.add_argument('--progress', action='store_true',
                        help='Show yt-dlp progress bar and log output to Logs/yt-dlp.log')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose (DEBUG) logging')
    parser.add_argument('--show-urls', action='store_true',
                        help='Allow urllib3/requests to log URLs (WARNING: may expose Slack webhook URL)')
    parser.add_argument('--rerun', action='store_true',
                        help='Reuse URL from previous run (stored in Data/last_url.txt). '
                             'Ignored if video_url is provided.')
    parser.add_argument('--title',
                        help='Custom title for output filename (ignored for playlists)')
    parser.add_argument('--artist',
                        help='Custom artist tag (ignored for playlists)')
    parser.add_argument('--album',
                        help='Custom album tag (ignored for playlists)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {version}')
    parser.add_argument('--list-chapters-only', action='store_true',
                        help='List chapters, create segments CSV, then download video and stop. '
                             'Aborts if the video has no chapters.')

    audio_group = parser.add_mutually_exclusive_group()
    audio_group.add_argument('--with-audio', action='store_true',
                             help='Also extract audio (format specified by --audio-format)')
    audio_group.add_argument('--only-audio', action='store_true',
                             help='Delete video files after extraction')
    audio_group.add_argument('--ertflix-program', action='store_true',
                             help='ERTFlix program mode: download video only (resolves token URLs, ignores audio flags)'
                             )

    return parser.parse_args(argv)


def parse_and_validate_audio_formats(audio_format_str: str) -> list[str]:
    """Parse comma-separated audio formats, validate, and deduplicate.

    Args:
        audio_format_str: Comma-separated audio format string (e.g., 'mp3,m4a').

    Returns:
        list[str]: Deduplicated list of valid format strings.
    """
    audio_formats = [fmt.strip() for fmt in audio_format_str.split(',')]
    invalid_formats = [fmt for fmt in audio_formats if fmt not in VALID_AUDIO_FORMATS]
    if invalid_formats:
        logger.error(f"Invalid audio format(s): {', '.join(invalid_formats)}")
        logger.error(f"Valid formats are: {', '.join(sorted(VALID_AUDIO_FORMATS))}")
        sys.exit(1)
    seen: set[str] = set()
    deduplicated: list[str] = []
    for fmt in audio_formats:
        if fmt not in seen:
            seen.add(fmt)
            deduplicated.append(fmt)
    return deduplicated


def get_custom_metadata(
    args: argparse.Namespace,
    url_is_playlist: bool,
) -> tuple[str | None, str | None, str | None]:
    """Handle --title, --artist, --album options with interactive prompts.

    Prompts the user if value starts with 'ask'/'prompt'. Warns and clears
    the value if used with a playlist.

    Args:
        args: Parsed command-line arguments.
        url_is_playlist: Whether the URL is a playlist.

    Returns:
        tuple[str | None, str | None, str | None]: (custom_title, custom_artist, custom_album)
    """
    custom_title = args.title
    if custom_title:
        if custom_title.lower().startswith(('ask', 'prompt')):
            custom_title = input('Enter custom title : ').strip() or None
        if custom_title and url_is_playlist:
            logger.warning('--title is ignored for playlists')
            custom_title = None

    custom_artist = args.artist
    if custom_artist:
        if custom_artist.lower().startswith(('ask', 'prompt')):
            custom_artist = input('Enter custom artist: ').strip() or None
        if custom_artist and url_is_playlist:
            logger.warning('--artist is ignored for playlists')
            custom_artist = None

    custom_album = args.album
    if custom_album:
        if custom_album.lower().startswith(('ask', 'prompt')):
            custom_album = input('Enter custom album : ').strip() or None
        if custom_album and url_is_playlist:
            logger.warning('--album is ignored for playlists')
            custom_album = None

    return custom_title, custom_artist, custom_album


def validate_list_chapters_only(args: argparse.Namespace) -> None:
    """Abort if --list-chapters-only is combined with conflicting flags.

    Args:
        args: Parsed command-line arguments.
    """
    if not args.list_chapters_only:
        return
    conflicting = []
    if args.with_audio:
        conflicting.append('--with-audio')
    if args.only_audio:
        conflicting.append('--only-audio')
    if args.subs:
        conflicting.append('--subs')
    if args.split_chapters:
        conflicting.append('--split-chapters')
    if conflicting:
        logger.error('--list-chapters-only cannot be combined with: %s', ', '.join(conflicting))
        sys.exit(1)


def determine_audio_mode(args: argparse.Namespace, audio_formats: list[str]) -> bool:
    """Determine whether audio extraction is needed.

    Forces video-only mode for ERTFlix program downloads.

    Args:
        args: Parsed command-line arguments (modified in place for ERTFlix mode).
        audio_formats: List of requested audio formats.

    Returns:
        bool: True if audio extraction is needed.
    """
    if args.ertflix_program:
        logger.info('ERTFlix program mode: downloading video only (audio extraction disabled)')
        args.only_audio = False
        args.with_audio = False
        return False
    logger.info(f'Requested audio formats: {", ".join(audio_formats)}')
    return args.with_audio or args.only_audio
