"""Using yt-dlp, download videos from URL, and extract the MP3 files."""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

from funcs_for_main_yt_dlp import (DownloadOptions, count_files,
                                   extract_audio_with_ytdlp,
                                   format_elapsed_time, generate_session_id,
                                   get_audio_dir_for_format, get_ffmpeg_path,
                                   get_ytdlp_path, get_ytdlp_version,
                                   organize_and_sanitize_files,
                                   process_audio_tags, remux_video_chapters,
                                   run_yt_dlp, validate_and_get_url)
from funcs_notifications import (GmailNotifier, NotificationData, SlackNotifier,
                                 send_all_notifications)
from funcs_video_info import (create_chapters_csv,
                              display_chapters_and_confirm, get_chapter_count,
                              get_video_info, is_playlist)
from funcs_utils import setup_logging
from project_defs import (DEFAULT_AUDIO_FORMAT, VALID_AUDIO_FORMATS,
                          VIDEO_OUTPUT_DIR)

SLACK_WEBHOOK: str | None = None
GMAIL_PARAMS: dict[str, str] | None = None
try:
    from git_excluded import SLACK_WEBHOOK  # type: ignore[assignment,no-redef]
except ImportError:
    pass
try:
    from git_excluded import GMAIL_PARAMS  # type: ignore[assignment,no-redef,attr-defined]
except ImportError:
    pass

# Version corresponds to the latest changelog entry timestamp
VERSION = '2026-02-28-1504'

logger = logging.getLogger(__name__)


def _cleanup_leftover_files(video_folder: Path) -> None:
    """Remove leftover *.ytdl and *.part files from cancelled downloads.

    Args:
        video_folder: Path to the video output directory
    """
    if not video_folder.exists():
        return

    leftover_patterns = ['*.ytdl', '*.part']
    removed_count = 0

    for pattern in leftover_patterns:
        for leftover_file in video_folder.glob(pattern):
            try:
                leftover_file.unlink()
                logger.debug(f"Removed leftover file: {leftover_file.name}")
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove {leftover_file.name}: {e}")

    if removed_count > 0:
        logger.info(f'Cleaned up {removed_count} leftover file(s) from previous cancelled downloads')


def _check_output_dirs_empty(
    only_audio: bool,
    need_audio: bool,
    audio_formats: list[str]
) -> None:
    """Abort if any output directory is non-empty (for split-chapters runs)."""
    dirs_to_check: list[Path] = []

    if not only_audio:
        dirs_to_check.append(Path(VIDEO_OUTPUT_DIR))

    if need_audio:
        for fmt in audio_formats:
            dirs_to_check.append(Path(get_audio_dir_for_format(audio_format=fmt)))

    non_empty = [d for d in dirs_to_check if d.exists() and any(d.iterdir())]

    if non_empty:
        dir_list = ', '.join(f"'{d}'" for d in non_empty)
        logger.error(
            f'Output director{"ies" if len(non_empty) > 1 else "y"} {dir_list} '
            f'is not empty. Copy any files you want to keep to another location, '
            f'then clear the director{"ies" if len(non_empty) > 1 else "y"} and run again.'
        )
        sys.exit(1)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and return command-line arguments.

    Args:
        argv: Command-line arguments to parse. If None, uses sys.argv.
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
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('--list-chapters-only', action='store_true',
                        help='List chapters, create segments CSV, then download video and stop. '
                             'Aborts if the video has no chapters.')

    audio_group = parser.add_mutually_exclusive_group()
    audio_group.add_argument('--with-audio', action='store_true',
                             help='Also extract audio (format specified by --audio-format)')
    audio_group.add_argument('--only-audio', action='store_true',
                             help='Delete video files after extraction')
    audio_group.add_argument('--ertflix-program', action='store_true',
                             help='ERTFlix program mode: download video only (resolves token URLs, ignores audio flags)')

    return parser.parse_args(argv)


def _parse_and_validate_audio_formats(audio_format_str: str) -> list[str]:
    """Parse comma-separated audio formats, validate, and deduplicate.

    Args:
        audio_format_str: Comma-separated audio format string (e.g., 'mp3,m4a')

    Returns:
        Deduplicated list of valid format strings
    """
    audio_formats = [fmt.strip() for fmt in audio_format_str.split(',')]

    invalid_formats = [fmt for fmt in audio_formats if fmt not in VALID_AUDIO_FORMATS]
    if invalid_formats:
        logger.error(f"Invalid audio format(s): {', '.join(invalid_formats)}")
        logger.error(f"Valid formats are: {', '.join(sorted(VALID_AUDIO_FORMATS))}")
        sys.exit(1)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    deduplicated: list[str] = []
    for fmt in audio_formats:
        if fmt not in seen:
            seen.add(fmt)
            deduplicated.append(fmt)
    return deduplicated


def _resolve_url(args: argparse.Namespace, yt_dlp_exe: str) -> str:
    """Resolve the video URL from arguments, interactive input, or --rerun.

    Handles --rerun flag, interactive URL prompting (3 retries), ERTFlix timeout
    detection (sets args.video_download_timeout as side effect), URL validation
    and resolution, and saves the resolved URL for future --rerun.

    Args:
        args: Parsed command-line arguments (modified in place for timeout/URL)
        yt_dlp_exe: Path to yt-dlp executable

    Returns:
        Resolved URL string
    """
    # Handle --rerun flag: load URL from previous run if requested
    last_url_file = Path('Data') / 'last_url.txt'
    if args.rerun and not args.video_url:
        if last_url_file.exists():
            args.video_url = last_url_file.read_text().strip()
            logger.info(f'Reusing URL from previous run: {args.video_url}')
        else:
            logger.error('No previous URL found in Data/last_url.txt')
            sys.exit(1)

    # In interactive mode, prompt for URL
    if not args.video_url:
        from funcs_video_info import validate_video_url
        for attempt in range(3):  # MAX_URL_RETRIES
            url_input = input('Enter the YouTube URL: ').strip()
            is_valid, error_msg = validate_video_url(url=url_input)
            if is_valid:
                args.video_url = url_input
                break
            logger.error(f'Invalid URL: {error_msg}')
            if attempt < 2:
                logger.info(f'Please try again ({2 - attempt} attempts remaining)')
            else:
                logger.error('Maximum retry attempts reached. Exiting.')
                sys.exit(1)

    # Determine timeout from ORIGINAL URL before resolution
    # This ensures ERTFlix URLs get the correct timeout even after CDN resolution
    from funcs_for_main_yt_dlp import is_ertflix_token_url
    from funcs_video_info import get_timeout_for_url
    if is_ertflix_token_url(url=args.video_url) and args.video_download_timeout is None:
        original_timeout = get_timeout_for_url(url=args.video_url)
        args.video_download_timeout = original_timeout
        logger.info(f'ERTFlix URL detected, using timeout: {original_timeout}s (based on original domain)')

    # Validate and resolve URL (ERTFlix token URLs get resolved to playback URLs)
    resolved_url = validate_and_get_url(provided_url=args.video_url, ytdlp_path=Path(yt_dlp_exe))

    # Save URL for future --rerun
    last_url_file.parent.mkdir(exist_ok=True)
    last_url_file.write_text(resolved_url)

    return resolved_url


def _get_custom_metadata(
    args: argparse.Namespace,
    url_is_playlist: bool
) -> tuple[str | None, str | None, str | None]:
    """Handle --title, --artist, --album options with interactive prompts.

    Prompts user if value starts with 'ask'/'prompt'. Warns and clears
    if used with a playlist.

    Args:
        args: Parsed command-line arguments
        url_is_playlist: Whether the URL is a playlist

    Returns:
        Tuple of (custom_title, custom_artist, custom_album)
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


def _detect_chapters(
    yt_dlp_exe: str,
    video_url: str,
    video_download_timeout: int | None,
    url_is_playlist: bool,
    show_chapters: bool
) -> tuple[bool, dict | None, str | None, str | None, dict[int, str]]:
    """Detect chapters and fetch video info if chapters exist.

    Args:
        yt_dlp_exe: Path to yt-dlp executable
        video_url: Video URL to check
        video_download_timeout: Timeout for video downloads
        url_is_playlist: Whether the URL is a playlist
        show_chapters: Whether to display chapters and build name map

    Returns:
        Tuple of (has_chapters, video_info, uploader_name, video_title, chapter_name_map)
    """
    if url_is_playlist:
        logger.info('URL is a playlist, not extracting chapters')
        return False, None, None, None, {}

    chapters_count = get_chapter_count(
        ytdlp_exe=Path(yt_dlp_exe),
        playlist_url=video_url,
        video_download_timeout=video_download_timeout
    )
    has_chapters = chapters_count > 0

    if not has_chapters:
        return False, None, None, None, {}

    logger.info(f'Video has {chapters_count} chapters')
    video_info = get_video_info(
        yt_dlp_path=Path(yt_dlp_exe),
        url=video_url,
        video_download_timeout=video_download_timeout
    )
    uploader_name = video_info.get('uploader')
    video_title = video_info.get('title')
    if uploader_name and uploader_name not in ('NA', ''):
        logger.debug(f"Uploader for chapters: '{uploader_name}'")
    if video_title and video_title not in ('NA', ''):
        logger.debug(f"Video title for chapters: '{video_title}'")

    chapter_name_map: dict[int, str] = {}
    if show_chapters:
        chapter_name_map = display_chapters_and_confirm(video_info=video_info)

    return has_chapters, video_info, uploader_name, video_title, chapter_name_map


def _validate_list_chapters_only(args: argparse.Namespace) -> None:
    """Validate --list-chapters-only is not combined with conflicting flags.

    Args:
        args: Parsed command-line arguments
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


def _determine_audio_mode(args: argparse.Namespace, audio_formats: list[str]) -> bool:
    """Determine whether audio extraction is needed.

    Handles ERTFlix program mode (forces video-only) and normal mode.

    Args:
        args: Parsed command-line arguments (modified in place for ERTFlix mode)
        audio_formats: List of requested audio formats

    Returns:
        True if audio extraction is needed
    """
    if args.ertflix_program:
        logger.info('ERTFlix program mode: downloading video only (audio extraction disabled)')
        args.only_audio = False
        args.with_audio = False
        return False

    logger.info(f'Requested audio formats: {", ".join(audio_formats)}')
    return args.with_audio or args.only_audio


def _count_new_files(
    only_audio: bool,
    need_audio: bool,
    audio_formats: list[str],
    initial_video_count: int,
    initial_audio_count: int
) -> tuple[int, int]:
    """Count newly created video and audio files since download started.

    Args:
        only_audio: Whether only audio was requested (skip video counting)
        need_audio: Whether audio extraction was requested
        audio_formats: List of audio formats to count
        initial_video_count: File count before download started
        initial_audio_count: File count before download started

    Returns:
        Tuple of (new_video_count, new_audio_count)
    """
    video_count = 0
    audio_count = 0
    if not only_audio:
        final_video_count = count_files(
            directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv']
        )
        video_count = final_video_count - initial_video_count
    if need_audio:
        final_audio_count = 0
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            final_audio_count += count_files(directory=audio_dir, extensions=[f'.{audio_format}'])
        audio_count = final_audio_count - initial_audio_count
    return video_count, audio_count


def _execute_main(args: argparse.Namespace, args_dict: dict, start_time: float, session_id: str,
                  initial_video_count: int, initial_audio_count: int,
                  notifiers: list | None = None, notif_msg_suffix: str = '') -> None:
    """Execute the main download logic."""

    audio_formats = _parse_and_validate_audio_formats(audio_format_str=args.audio_format)
    _validate_list_chapters_only(args=args)
    need_audio = _determine_audio_mode(args=args, audio_formats=audio_formats)

    # Detect platform and set appropriate executable path
    yt_dlp_exe = get_ytdlp_path()
    ytdlp_version = get_ytdlp_version(ytdlp_path=yt_dlp_exe)

    # Handle artists.json path relative to script location, not current working directory
    script_dir = Path(__file__).parent
    artists_json = script_dir / 'Data' / 'artists.json'
    if not artists_json.exists():
        logger.error(f"Artists database not found at '{artists_json}'")
        logger.error('Please ensure file exists in the project directory')
        sys.exit(1)

    # Resolve URL (handles --rerun, interactive input, ERTFlix timeout, validation)
    args.video_url = _resolve_url(args=args, yt_dlp_exe=yt_dlp_exe)
    logger.info(f'Processing URL: {args.video_url}')

    # Send start notification
    if notifiers:
        send_all_notifications(
            notifiers=notifiers,
            data=NotificationData(
                status='start',
                url=args.video_url,
                args_dict=args_dict,
                session_id=session_id,
                script_version=VERSION,
                ytdlp_version=ytdlp_version,
                notif_msg_suffix=notif_msg_suffix
            )
        )

    video_folder = Path(VIDEO_OUTPUT_DIR).resolve()

    # Pre-flight check for --split-chapters: abort if output dirs are non-empty
    if args.split_chapters:
        _check_output_dirs_empty(
            only_audio=args.only_audio,
            need_audio=need_audio,
            audio_formats=audio_formats
        )

    if not args.only_audio:
        video_folder.mkdir(parents=True, exist_ok=True)
        _cleanup_leftover_files(video_folder=video_folder)
    if need_audio:
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            audio_dir.mkdir(parents=True, exist_ok=True)

    url_is_playlist = is_playlist(url=args.video_url)

    if args.list_chapters_only and url_is_playlist:
        logger.error('--list-chapters-only does not support playlist URLs. Provide a single video URL.')
        sys.exit(1)

    # Get custom metadata (--title, --artist, --album)
    custom_title, custom_artist, custom_album = _get_custom_metadata(
        args=args, url_is_playlist=url_is_playlist
    )

    # Detect chapters and fetch video info
    has_chapters, video_info, uploader_name, video_title, chapter_name_map = _detect_chapters(
        yt_dlp_exe=yt_dlp_exe,
        video_url=args.video_url,
        video_download_timeout=args.video_download_timeout,
        url_is_playlist=url_is_playlist,
        show_chapters=args.split_chapters or args.list_chapters_only
    )

    # --list-chapters-only requires the video to have chapters
    if args.list_chapters_only and not has_chapters:
        logger.error('--list-chapters-only: video has no chapters. Aborting.')
        sys.exit(1)

    # Create download options dataclass for common parameters
    download_opts = DownloadOptions(
        ytdlp_exe=yt_dlp_exe,
        url=args.video_url,
        has_chapters=has_chapters,
        split_chapters=args.split_chapters,
        is_it_playlist=url_is_playlist,
        show_progress=args.progress,
        video_download_timeout=args.video_download_timeout,
        custom_title=custom_title,
        custom_artist=custom_artist,
        custom_album=custom_album
    )

    # Create chapters CSV for user reference (always when split_chapters or list_chapters_only is active)
    if (args.split_chapters or args.list_chapters_only) and has_chapters:
        chapters_dir = Path('yt-chapters')
        chapters_dir.mkdir(parents=True, exist_ok=True)
        create_chapters_csv(video_info=video_info, output_dir=chapters_dir, video_title=video_title or 'Unknown')

    # Download videos if requested
    if not args.only_audio:
        run_yt_dlp(opts=download_opts, video_folder=video_folder, get_subs=args.subs, write_json=args.json)
        if args.list_chapters_only:
            logger.info('--list-chapters-only: chapters CSV created and video downloaded. Done.')
            return
        if args.split_chapters and has_chapters:
            remux_video_chapters(ffmpeg_path=get_ffmpeg_path(), video_folder=video_folder,
                                 chapters=video_info.get('chapters', []),
                                 video_title=video_title)

    # Download audios if requested
    if need_audio:
        extract_audio_with_ytdlp(opts=download_opts, audio_formats=audio_formats)

    # Organize chapter files and sanitize filenames
    original_names = organize_and_sanitize_files(
        video_folder=video_folder,
        audio_formats=audio_formats,
        has_chapters=has_chapters,
        only_audio=args.only_audio,
        need_audio=need_audio,
        chapter_name_map=chapter_name_map
    )

    # Process audio tags
    if need_audio:
        process_audio_tags(
            audio_formats=audio_formats,
            artists_json=artists_json,
            has_chapters=has_chapters,
            uploader_name=uploader_name,
            video_title=video_title,
            original_names=original_names
        )

    # Send success notification
    if notifiers:
        elapsed_time = format_elapsed_time(time.time() - start_time)
        video_count, audio_count = _count_new_files(
            only_audio=args.only_audio, need_audio=need_audio,
            audio_formats=audio_formats,
            initial_video_count=initial_video_count,
            initial_audio_count=initial_audio_count
        )
        send_all_notifications(
            notifiers=notifiers,
            data=NotificationData(
                status='success',
                url=args.video_url,
                args_dict=args_dict,
                session_id=session_id,
                elapsed_time=elapsed_time,
                video_count=video_count,
                audio_count=audio_count,
                notif_msg_suffix=notif_msg_suffix
            )
        )
    logger.info('Download completed successfully')


def main() -> None:
    args = parse_arguments()

    # Setup logging (must be done early)
    setup_logging(verbose=args.verbose, log_to_file=not args.no_log_file, show_urls=args.show_urls)

    # Store args as dict for Slack notification
    args_dict = {
        'video_url': args.video_url,
        'audio_format': args.audio_format,
        'split_chapters': args.split_chapters,
        'list_chapters_only': args.list_chapters_only,
        'video_download_timeout': args.video_download_timeout,
        'subs': args.subs,
        'json': args.json,
        'with_audio': args.with_audio,
        'only_audio': args.only_audio,
        'title': args.title,
        'artist': args.artist,
        'album': args.album,
        'rerun': args.rerun
    }

    # Generate session ID for Slack notifications
    session_id = generate_session_id()

    # Record start time
    start_time = time.time()

    # Count existing files before download to track only newly created files
    audio_formats_str = args.audio_format
    audio_formats = [fmt.strip() for fmt in audio_formats_str.split(',')]
    initial_video_count = 0
    initial_audio_count = 0
    if not args.only_audio:
        initial_video_count = count_files(directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv'])
    if args.with_audio or args.only_audio:
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            initial_audio_count += count_files(directory=audio_dir, extensions=[f'.{audio_format}'])

    # Build notifiers list (check NOTIFICATIONS env var)
    notifiers: list = []
    notifications_enabled = os.getenv('NOTIFICATIONS', '').strip().upper()

    if notifications_enabled in ('', 'N', 'NO'):
        # No notifications (empty string treated same as N/NO)
        logger.info('Notifications disabled (NOTIFICATIONS env var: empty/N/NO)')
    elif notifications_enabled == 'S':
        # Slack only
        _slack = SlackNotifier(webhook_url=SLACK_WEBHOOK)
        if _slack.is_configured():
            notifiers.append(_slack)
            logger.debug('Slack notifications enabled (Gmail disabled)')
        else:
            logger.warning('Slack requested but not configured')
    elif notifications_enabled == 'G':
        # Gmail only
        _gmail = GmailNotifier(gmail_params=GMAIL_PARAMS)
        if _gmail.is_configured():
            notifiers.append(_gmail)
            logger.debug('Gmail notifications enabled (Slack disabled)')
        else:
            logger.warning('Gmail requested but not configured')
    elif notifications_enabled == 'ALL':
        # Both
        _slack = SlackNotifier(webhook_url=SLACK_WEBHOOK)
        if _slack.is_configured():
            notifiers.append(_slack)
        _gmail = GmailNotifier(gmail_params=GMAIL_PARAMS)
        if _gmail.is_configured():
            notifiers.append(_gmail)
        if notifiers:
            logger.debug('Both Slack and Gmail notifications enabled')
    else:
        # Invalid value - log warning, disable notifications
        logger.warning(f'Invalid NOTIFICATIONS value: "{notifications_enabled}". '
                       f'Expected: empty/N/NO (none), S (Slack), G (Gmail), ALL (both). '
                       f'Defaulting to no notifications.')

    # Get NOTIF_MSG suffix (if set)
    notif_msg_suffix = os.getenv('NOTIF_MSG', '').strip()
    if notif_msg_suffix:
        logger.debug(f'Notification message suffix: "{notif_msg_suffix}"')

    try:
        _execute_main(args=args, args_dict=args_dict, start_time=start_time, session_id=session_id,
                      initial_video_count=initial_video_count, initial_audio_count=initial_audio_count,
                      notifiers=notifiers, notif_msg_suffix=notif_msg_suffix)
    except KeyboardInterrupt:
        logger.warning('Download cancelled by user (CTRL-C)')
        if notifiers:
            elapsed_time = format_elapsed_time(time.time() - start_time)
            need_audio = args.with_audio or args.only_audio
            video_count, audio_count = _count_new_files(
                only_audio=args.only_audio, need_audio=need_audio,
                audio_formats=audio_formats,
                initial_video_count=initial_video_count,
                initial_audio_count=initial_audio_count
            )
            send_all_notifications(
                notifiers=notifiers,
                data=NotificationData(
                    status='cancelled',
                    url=args.video_url or 'N/A',
                    args_dict=args_dict,
                    session_id=session_id,
                    elapsed_time=elapsed_time,
                    video_count=video_count,
                    audio_count=audio_count,
                    notif_msg_suffix=notif_msg_suffix
                )
            )
        logger.info('Exiting...')
        sys.exit(130)  # Standard exit code for CTRL-C
    except Exception as e:
        logger.exception(f'Download failed: {e}')
        if notifiers:
            elapsed_time = format_elapsed_time(time.time() - start_time)
            need_audio = args.with_audio or args.only_audio
            video_count, audio_count = _count_new_files(
                only_audio=args.only_audio, need_audio=need_audio,
                audio_formats=audio_formats,
                initial_video_count=initial_video_count,
                initial_audio_count=initial_audio_count
            )
            send_all_notifications(
                notifiers=notifiers,
                data=NotificationData(
                    status='failure',
                    url=args.video_url or 'N/A',
                    args_dict=args_dict,
                    session_id=session_id,
                    elapsed_time=elapsed_time,
                    video_count=video_count,
                    audio_count=audio_count,
                    failure_reason=str(e),
                    notif_msg_suffix=notif_msg_suffix
                )
            )
        sys.exit(1)


if __name__ == '__main__':
    main()
