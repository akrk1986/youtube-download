"""Using yt-dlp, download videos from YouTube URL, and extract the MP3 files."""
import argparse
import glob
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

# Version corresponds to the latest changelog entry timestamp
VERSION = '2025-10-09 18:45:00'

from logger_config import setup_logging
from funcs_for_main_yt_dlp import validate_and_get_url, organize_and_sanitize_files, process_audio_tags
from funcs_utils import get_video_info, is_playlist, get_chapter_count, sanitize_url_for_subprocess, get_timeout_for_url
from project_defs import (
    DEFAULT_AUDIO_QUALITY, DEFAULT_AUDIO_FORMAT, VALID_AUDIO_FORMATS,
    YT_DLP_WRITE_JSON_FLAG, YT_DLP_SPLIT_CHAPTERS_FLAG,
    YT_DLP_IS_PLAYLIST_FLAG, VIDEO_OUTPUT_DIR, AUDIO_OUTPUT_DIR
)

logger = logging.getLogger(__name__)


def _run_yt_dlp(ytdlp_exe: Path, playlist_url: str, video_folder: str, get_subs: bool,
                write_json: bool, has_chapters: bool, split_chapters: bool, is_it_playlist: bool) -> None:
    """Extract videos from YouTube playlist/video with yt-dlp. Include subtitles if requested."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(playlist_url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(playlist_url)

    yt_dlp_cmd = [
        ytdlp_exe,
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        '--merge-output-format', 'mp4',
        '--embed-metadata',
        '--add-metadata',
        '--parse-metadata', 'webpage_url:%(meta_comment)s',  # Store URL in comment metadata
        '-o', os.path.join(video_folder, '%(title)s.%(ext)s'),
        sanitized_url
    ]
    if is_it_playlist:
        yt_dlp_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if write_json:
        yt_dlp_cmd[1:1] = [YT_DLP_WRITE_JSON_FLAG]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]
    if get_subs:
        # Extract subtitles in Greek, English, Hebrew
        yt_dlp_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    logger.info('Downloading videos with yt-dlp...')
    logger.info(f'Command: {yt_dlp_cmd}')

    # Run download with error handling
    # Note: Some videos in playlists may be unavailable, which is expected
    try:
        result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
        logger.info('Video download completed successfully')
        if result.stdout:
            logger.debug(f'yt-dlp output: {result.stdout}')
    except subprocess.TimeoutExpired:
        logger.error(f"Video download timed out after {timeout} seconds for URL '{playlist_url}'")
        if not is_it_playlist:
            raise RuntimeError(f"Download timed out for '{playlist_url}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"Video download failed for URL '{playlist_url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        # For playlists, partial failure is acceptable
        if is_it_playlist:
            logger.warning(f"Some videos in playlist '{playlist_url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download video from '{playlist_url}': {e.stderr}")

def _extract_single_format(ytdlp_exe: Path, playlist_url: str, audio_folder: str,
                          has_chapters: bool, split_chapters: bool, is_it_playlist: bool,
                          format_type: str, artist_pat: str | None = None, album_artist_pat: str | None = None) -> None:
    """Extract audio in a single format using yt-dlp."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(playlist_url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(playlist_url)

    # Create format-specific subfolder
    format_folder = os.path.join(audio_folder, format_type)
    os.makedirs(format_folder, exist_ok=True)

    # For FLAC (lossless), use best quality (0); for lossy formats use default quality
    audio_quality = '0' if format_type == 'flac' else DEFAULT_AUDIO_QUALITY

    yt_dlp_cmd = [
        ytdlp_exe,
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', format_type,
        '--audio-quality', audio_quality,
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',
        '-o', os.path.join(format_folder, '%(title)s.%(ext)s'),
        sanitized_url
    ]

    if is_it_playlist:
        yt_dlp_cmd[1:1] = [YT_DLP_IS_PLAYLIST_FLAG]
    if artist_pat and album_artist_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', artist_pat,
                           '--parse-metadata', album_artist_pat,
                           ]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [YT_DLP_SPLIT_CHAPTERS_FLAG]

    logger.info(f'Downloading and extracting {format_type.upper()} audio with yt-dlp')
    logger.info(f'Command: {yt_dlp_cmd}')

    # Run download with error handling
    # Note: Some videos in playlists may be unavailable, which is expected
    try:
        result = subprocess.run(yt_dlp_cmd, check=True, capture_output=True, text=True, timeout=timeout)
        logger.info(f'{format_type.upper()} audio download completed successfully')
        if result.stdout:
            logger.debug(f'yt-dlp output: {result.stdout}')
    except subprocess.TimeoutExpired:
        logger.error(f"{format_type.upper()} audio download timed out after {timeout} seconds for URL '{playlist_url}'")
        if not is_it_playlist:
            raise RuntimeError(f"Audio download timed out for '{playlist_url}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"{format_type.upper()} audio download failed for URL '{playlist_url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        # For playlists, partial failure is acceptable
        if is_it_playlist:
            logger.warning(f"Some videos in playlist '{playlist_url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download {format_type.upper()} audio from '{playlist_url}': {e.stderr}")

def _extract_audio_with_ytdlp(ytdlp_exe: Path, playlist_url: str, audio_folder: str,
                              has_chapters: bool, split_chapters: bool, is_it_playlist: bool, audio_formats: list[str]) -> None:
    """Use yt-dlp to download and extract audio with metadata and thumbnail."""

    # For a single video, check if video has 'artist' or 'uploader' tags.
    # Use either to embed 'artist' and 'albumartist' tags in the audio file.
    artist_pat = album_artist_pat = None

    if is_it_playlist:
        have_artist = have_uploader = False
        logger.info('URL is a playlist, cannot extract artist/uploader')
    else:
        video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=playlist_url)
        artist = video_info.get('artist')
        uploader = video_info.get('uploader')
        have_artist = artist and artist not in ('NA', '')
        have_uploader = uploader and uploader not in ('NA', '')

        if have_artist:
            artist_pat = 'artist:%(artist)s'
            album_artist_pat = 'album_artist:%(artist)s'
            logger.info(f"Video has artist: '{artist}'")
        elif have_uploader:
            artist_pat = 'artist:%(uploader)s'
            album_artist_pat = 'album_artist:%(uploader)s'
            logger.info(f"Video has uploader: '{uploader}'")

    # Extract each requested audio format
    for audio_format in audio_formats:
        _extract_single_format(ytdlp_exe, playlist_url, audio_folder, has_chapters,
                              split_chapters, is_it_playlist, audio_format, artist_pat, album_artist_pat)

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Download YouTube playlist/video, optionally with subtitles.')
    parser.add_argument('playlist_url', nargs='?', help='YouTube playlist/video URL')
    parser.add_argument('--with-audio', action='store_true', help='Also extract audio (format specified by --audio-format)')
    parser.add_argument('--audio-format', default=DEFAULT_AUDIO_FORMAT, help=f'Audio format for extraction: mp3, m4a, flac, or comma-separated (e.g., mp3,m4a) (default: {DEFAULT_AUDIO_FORMAT})')
    parser.add_argument('--only-audio', action='store_true', help='Delete video files after extraction')
    parser.add_argument('--split-chapters', action='store_true', help='Split to chapters')
    parser.add_argument('--subs', action='store_true', help='Download subtitles')
    parser.add_argument('--json', action='store_true', help='Write JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose (DEBUG) logging')
    parser.add_argument('--no-log-file', action='store_true', help='Disable logging to file')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    args = parser.parse_args()

    # Setup logging (must be done early)
    setup_logging(verbose=args.verbose, log_to_file=not args.no_log_file)

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
    audio_formats = [fmt for fmt in audio_formats if not (fmt in seen or seen.add(fmt))]

    logger.info(f'Audio formats: {", ".join(audio_formats)}')

    need_audio = args.with_audio or args.only_audio

    # Detect platform and set appropriate executable paths
    system_platform = platform.system().lower()

    if system_platform == 'windows':
        # Windows paths
        home_dir = Path.home()
        yt_dlp_dir = home_dir / 'Apps' / 'yt-dlp'
        yt_dlp_exe = yt_dlp_dir / 'yt-dlp.exe'
    else:
        # Linux/Mac - use system-wide installations
        yt_dlp_exe = 'yt-dlp'  # Should be in PATH

    # Handle artists.json path relative to script location, not current working directory
    script_dir = Path(__file__).parent
    artists_json = script_dir / 'Data' / 'artists.json'

    # Validate artists.json exists
    if not artists_json.exists():
        logger.error(f'Artists database not found at {artists_json}')
        logger.error('Please ensure Data/artists.json exists in the project directory')
        sys.exit(1)

    # Verify executables exist
    if system_platform == 'windows':
        if not Path(yt_dlp_exe).exists():
            logger.error(f"YT-DLP executable not found at path '{yt_dlp_exe}'")
            logger.error(f"Please ensure yt-dlp is installed in '{yt_dlp_dir}'")
            sys.exit(1)
    else:
        # For Linux/Mac, check if commands are available in PATH
        try:
            subprocess.run([yt_dlp_exe, '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f'YT-DLP not found in PATH: {e}')
            logger.error('Install with: pip install yt-dlp')
            sys.exit(1)

    # Validate and get URL
    args.playlist_url = validate_and_get_url(args.playlist_url)
    logger.info(f'Processing URL: {args.playlist_url}')

    video_folder = os.path.abspath(VIDEO_OUTPUT_DIR)
    audio_folder = os.path.abspath(AUDIO_OUTPUT_DIR)
    if not args.only_audio:
        os.makedirs(video_folder, exist_ok=True)
    if need_audio:
        os.makedirs(audio_folder, exist_ok=True)

    url_is_playlist = is_playlist(url=args.playlist_url)
    uploader_name = None  # Initialize uploader name for chapter processing
    video_title = None  # Initialize video title for chapter processing

    if not url_is_playlist:
        chapters_count = get_chapter_count(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url)
        has_chapters = chapters_count > 0
        logger.info(f'Video has {chapters_count} chapters')

        # Get uploader and title information for chapter processing
        if has_chapters:
            video_info = get_video_info(yt_dlp_path=yt_dlp_exe, url=args.playlist_url)
            uploader_name = video_info.get('uploader')
            video_title = video_info.get('title')
            if uploader_name and uploader_name not in ('NA', ''):
                logger.debug(f"Uploader for chapters: '{uploader_name}'")
            if video_title and video_title not in ('NA', ''):
                logger.debug(f"Video title for chapters: '{video_title}'")
    else:
        logger.info('URL is a playlist, not extracting chapters')
        has_chapters = False

    # Download videos if requested
    if not args.only_audio:
        _run_yt_dlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, video_folder=video_folder, get_subs=args.subs,
                    write_json=args.json, split_chapters=args.split_chapters, has_chapters=has_chapters,
                    is_it_playlist=url_is_playlist)

    # Download audios if requested
    if need_audio:
        # Run yt-dlp to download videos, and let yt-dlp extract audio and add tags
        _extract_audio_with_ytdlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, audio_folder=audio_folder,
                                  split_chapters=args.split_chapters, has_chapters=has_chapters,
                                  is_it_playlist=url_is_playlist, audio_formats=audio_formats)

    # Organize chapter files and sanitize filenames
    original_names = organize_and_sanitize_files(
        video_folder=Path(video_folder),
        audio_folder=Path(audio_folder),
        audio_formats=audio_formats,
        has_chapters=has_chapters,
        only_audio=args.only_audio,
        need_audio=need_audio
    )

    # Process audio tags
    if need_audio:
        process_audio_tags(
            audio_folder=Path(audio_folder),
            audio_formats=audio_formats,
            artists_json=artists_json,
            has_chapters=has_chapters,
            uploader_name=uploader_name,
            video_title=video_title,
            original_names=original_names
        )

if __name__ == '__main__':
    main()
