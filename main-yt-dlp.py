"""Using yt-dlp, download videos from URL, and extract the MP3 files."""
import argparse
import logging
import sys
import time
from pathlib import Path

from funcs_for_main_yt_dlp import (count_files, format_elapsed_time,
                                   generate_session_id, get_audio_dir_for_format,
                                   get_ffmpeg_path, get_ytdlp_path,
                                   organize_and_sanitize_files,
                                   process_audio_tags, validate_and_get_url)
from funcs_slack_notify import send_slack_notification
from funcs_video_info import (create_chapters_csv,
                              display_chapters_and_confirm, get_chapter_count,
                              get_video_info, is_playlist)
from funcs_yt_dlp_download import (DownloadOptions, extract_audio_with_ytdlp,
                                   remux_video_chapters, run_yt_dlp)
from logger_config import setup_logging
from project_defs import (DEFAULT_AUDIO_FORMAT, VALID_AUDIO_FORMATS,
                          VIDEO_OUTPUT_DIR)

SLACK_WEBHOOK: str | None
try:
    from git_excluded import SLACK_WEBHOOK
except ImportError:
    SLACK_WEBHOOK = None

# Version corresponds to the latest changelog entry timestamp
VERSION = '2026-02-04-1646'

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Download YouTube playlist/video, optionally with subtitles.')
    parser.add_argument('video_url', nargs='?', help='Playlist/video URL')
    parser.add_argument('--audio-format', default=DEFAULT_AUDIO_FORMAT,
                        help='Audio format for extraction: mp3, m4a, flac, or comma-separated list '
                             f'(e.g., mp3,m4a). (default: {DEFAULT_AUDIO_FORMAT})')
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
                        help='Reuse URL from previous run (stored in Tests/last_url.txt). '
                             'Ignored if video_url is provided.')
    parser.add_argument('--title',
                        help='Custom title for output filename (ignored for playlists)')
    parser.add_argument('--artist',
                        help='Custom artist tag (ignored for playlists)')
    parser.add_argument('--album',
                        help='Custom album tag (ignored for playlists)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')

    audio_group = parser.add_mutually_exclusive_group()
    audio_group.add_argument('--with-audio', action='store_true',
                             help='Also extract audio (format specified by --audio-format)')
    audio_group.add_argument('--only-audio', action='store_true',
                             help='Delete video files after extraction')

    return parser.parse_args()


def _execute_main(args, args_dict: dict, start_time: float, session_id: str,
                  initial_video_count: int, initial_audio_count: int) -> None:
    """Execute the main download logic."""

    # Parse and validate audio formats
    audio_formats_str = args.audio_format
    audio_formats = [fmt.strip() for fmt in audio_formats_str.split(',')]

    # Validate each format
    invalid_formats = [fmt for fmt in audio_formats if fmt not in VALID_AUDIO_FORMATS]
    if invalid_formats:
        logger.error(f"Invalid audio format(s): {', '.join(invalid_formats)}")
        logger.error(f"Valid formats are: {', '.join(sorted(VALID_AUDIO_FORMATS))}")
        sys.exit(1)

    # Remove duplicates while preserving order
    seen = set()
    deduplicated_formats = []
    for fmt in audio_formats:
        if fmt not in seen:
            seen.add(fmt)
            deduplicated_formats.append(fmt)
    audio_formats = deduplicated_formats

    logger.info(f'Requested audio formats: {", ".join(audio_formats)}')

    need_audio = args.with_audio or args.only_audio

    # Detect platform and set appropriate executable path

    yt_dlp_exe = get_ytdlp_path()

    # Handle artists.json path relative to script location, not current working directory
    script_dir = Path(__file__).parent
    artists_json = script_dir / 'Data' / 'artists.json'

    # Validate artists.json exists
    if not artists_json.exists():
        logger.error(f"Artists database not found at '{artists_json}'")
        logger.error('Please ensure file exists in the project directory')
        sys.exit(1)

    # Handle --rerun flag: load URL from previous run if requested
    last_url_file = Path('Tests') / 'last_url.txt'
    if args.rerun and not args.video_url:
        if last_url_file.exists():
            args.video_url = last_url_file.read_text().strip()
            logger.info(f'Reusing URL from previous run: {args.video_url}')
        else:
            logger.error('No previous URL found in Tests/last_url.txt')
            sys.exit(1)

    # Validate and get URL
    args.video_url = validate_and_get_url(provided_url=args.video_url)
    logger.info(f'Processing URL: {args.video_url}')

    # Send start notification to Slack
    # SECURITY: SLACK_WEBHOOK must never be logged, even with --verbose
    if SLACK_WEBHOOK:
        send_slack_notification(
            webhook_url=SLACK_WEBHOOK,
            status='start',
            url=args.video_url,
            args_dict=args_dict,
            session_id=session_id
        )

    # Save URL for future --rerun
    last_url_file.parent.mkdir(exist_ok=True)
    last_url_file.write_text(args.video_url)

    video_folder = Path(VIDEO_OUTPUT_DIR).resolve()
    if not args.only_audio:
        video_folder.mkdir(parents=True, exist_ok=True)
    if need_audio:
        # Create audio directories for each requested format
        for audio_format in audio_formats:
            audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
            audio_dir.mkdir(parents=True, exist_ok=True)

    url_is_playlist = is_playlist(url=args.video_url)
    uploader_name = None  # Initialize uploader name for chapter processing
    video_title = None  # Initialize video title for chapter processing

    # Handle --title option
    custom_title = args.title
    if custom_title:
        # If title starts with 'ask' or 'prompt', prompt user for the actual title
        if custom_title.lower().startswith(('ask', 'prompt')):
            custom_title = input('Enter custom title : ').strip() or None

        # Warn if --title is used with a playlist
        if custom_title and url_is_playlist:
            logger.warning('--title is ignored for playlists')
            custom_title = None

    # Handle --artist option
    custom_artist = args.artist
    if custom_artist:
        if custom_artist.lower().startswith(('ask', 'prompt')):
            custom_artist = input('Enter custom artist: ').strip() or None
        if custom_artist and url_is_playlist:
            logger.warning('--artist is ignored for playlists')
            custom_artist = None

    # Handle --album option
    custom_album = args.album
    if custom_album:
        if custom_album.lower().startswith(('ask', 'prompt')):
            custom_album = input('Enter custom album : ').strip() or None
        if custom_album and url_is_playlist:
            logger.warning('--album is ignored for playlists')
            custom_album = None

    chapter_name_map = {}

    if not url_is_playlist:
        chapters_count = get_chapter_count(ytdlp_exe=Path(yt_dlp_exe), playlist_url=args.video_url,
                                            video_download_timeout=args.video_download_timeout)
        has_chapters = chapters_count > 0

        # Get uploader and title information for chapter processing
        if has_chapters:
            logger.info(f'Video has {chapters_count} chapters')
            video_info = get_video_info(yt_dlp_path=Path(yt_dlp_exe), url=args.video_url,
                                        video_download_timeout=args.video_download_timeout)
            uploader_name = video_info.get('uploader')
            video_title = video_info.get('title')
            if uploader_name and uploader_name not in ('NA', ''):
                logger.debug(f"Uploader for chapters: '{uploader_name}'")
            if video_title and video_title not in ('NA', ''):
                logger.debug(f"Video title for chapters: '{video_title}'")

            # Display chapters and build filename mapping if split-chapters is requested
            if args.split_chapters:
                chapter_name_map = display_chapters_and_confirm(video_info=video_info)
    else:
        logger.info('URL is a playlist, not extracting chapters')
        has_chapters = False

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

    # Download videos if requested
    if not args.only_audio:
        if args.split_chapters and has_chapters:
            create_chapters_csv(video_info=video_info, output_dir=video_folder, video_title=video_title or 'Unknown')
        run_yt_dlp(opts=download_opts, video_folder=video_folder, get_subs=args.subs, write_json=args.json)
        if args.split_chapters and has_chapters:
            remux_video_chapters(ffmpeg_path=get_ffmpeg_path(), video_folder=video_folder,
                                 chapters=video_info.get('chapters', []))

    # Download audios if requested
    if need_audio:
        # Run yt-dlp to download videos, and let yt-dlp extract audio and add tags
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
    # SECURITY: SLACK_WEBHOOK must never be logged, even with --verbose
    if SLACK_WEBHOOK:
        elapsed_time = format_elapsed_time(time.time() - start_time)
        # Count newly created files (difference between final and initial counts)
        video_count = 0
        audio_count = 0
        if not args.only_audio:
            final_video_count = count_files(directory=video_folder, extensions=['.mp4', '.webm', '.mkv'])
            video_count = final_video_count - initial_video_count
        if need_audio:
            final_audio_count = 0
            for audio_format in audio_formats:
                audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
                final_audio_count += count_files(directory=audio_dir, extensions=[f'.{audio_format}'])
            audio_count = final_audio_count - initial_audio_count
        send_slack_notification(
            webhook_url=SLACK_WEBHOOK,
            status='success',
            url=args.video_url,
            args_dict=args_dict,
            session_id=session_id,
            elapsed_time=elapsed_time,
            video_count=video_count,
            audio_count=audio_count
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

    try:
        _execute_main(args=args, args_dict=args_dict, start_time=start_time, session_id=session_id,
                      initial_video_count=initial_video_count, initial_audio_count=initial_audio_count)
    except KeyboardInterrupt:
        logger.warning('Download cancelled by user (CTRL-C)')
        # Send cancellation notification
        # SECURITY: SLACK_WEBHOOK must never be logged, even with --verbose
        if SLACK_WEBHOOK:
            elapsed_time = format_elapsed_time(time.time() - start_time)
            # Count newly created files before cancellation (difference between final and initial counts)
            video_count = 0
            audio_count = 0
            if not args.only_audio:
                final_video_count = count_files(directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv'])
                video_count = final_video_count - initial_video_count
            if args.with_audio or args.only_audio:
                final_audio_count = 0
                for audio_format in audio_formats:
                    audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
                    final_audio_count += count_files(directory=audio_dir, extensions=[f'.{audio_format}'])
                audio_count = final_audio_count - initial_audio_count
            send_slack_notification(
                webhook_url=SLACK_WEBHOOK,
                status='cancelled',
                url=args.video_url or 'N/A',
                args_dict=args_dict,
                session_id=session_id,
                elapsed_time=elapsed_time,
                video_count=video_count,
                audio_count=audio_count
            )
        logger.info('Exiting...')
        sys.exit(130)  # Standard exit code for CTRL-C
    except Exception as e:
        logger.exception(f'Download failed: {e}')
        # Send failure notification
        # SECURITY: SLACK_WEBHOOK must never be logged, even with --verbose
        if SLACK_WEBHOOK:
            elapsed_time = format_elapsed_time(time.time() - start_time)
            # Count newly created files before failure (difference between final and initial counts)
            video_count = 0
            audio_count = 0
            if not args.only_audio:
                final_video_count = count_files(directory=Path(VIDEO_OUTPUT_DIR), extensions=['.mp4', '.webm', '.mkv'])
                video_count = final_video_count - initial_video_count
            if args.with_audio or args.only_audio:
                final_audio_count = 0
                for audio_format in audio_formats:
                    audio_dir = Path(get_audio_dir_for_format(audio_format=audio_format))
                    final_audio_count += count_files(directory=audio_dir, extensions=[f'.{audio_format}'])
                audio_count = final_audio_count - initial_audio_count
            send_slack_notification(
                webhook_url=SLACK_WEBHOOK,
                status='failure',
                url=args.video_url or 'N/A',
                args_dict=args_dict,
                session_id=session_id,
                elapsed_time=elapsed_time,
                video_count=video_count,
                audio_count=audio_count,
                failure_reason=str(e)
            )
        sys.exit(1)


if __name__ == '__main__':
    main()
