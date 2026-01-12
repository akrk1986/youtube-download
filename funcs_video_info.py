"""Video information and URL validation utilities for yt-dlp scripts."""
import csv
import json
import logging
import os
import subprocess
import urllib.error
from pathlib import Path
from typing import Any

import yt_dlp

from funcs_url_extraction import is_valid_domain_url
from funcs_utils import get_cookie_args, sanitize_url_for_subprocess
from project_defs import (
    SUBPROCESS_TIMEOUT_FACEBOOK, SUBPROCESS_TIMEOUT_OTHER_SITES, SUBPROCESS_TIMEOUT_YOUTUBE,
    VALID_FACEBOOK_DOMAINS, VALID_OTHER_DOMAINS, VALID_YOUTUBE_DOMAINS
)

logger = logging.getLogger(__name__)


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f'{hours:02d}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def _seconds_to_hhmmss(seconds: float) -> str:
    """Convert seconds to HHMMSS format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f'{hours:02d}{minutes:02d}{secs:02d}'


def get_timeout_for_url(url: str, video_download_timeout: int | None = None) -> int:
    """
    Determine the appropriate subprocess timeout based on the URL domain.

    Args:
        url: The URL to check
        video_download_timeout: Optional timeout in seconds for video downloads.
                               If specified, this timeout is used for all sites.
                               If None, uses domain-specific defaults (300s for YouTube/Facebook, 3600s for others).

    Returns:
        int: Timeout in seconds
    """
    from urllib.parse import urlparse

    # If user specified a timeout, use it for all sites
    if video_download_timeout is not None:
        return video_download_timeout

    try:
        parsed = urlparse(url)

        # Check if it's a YouTube or Facebook domain
        if any(domain in parsed.netloc for domain in VALID_YOUTUBE_DOMAINS):
            return SUBPROCESS_TIMEOUT_YOUTUBE

        if any(domain in parsed.netloc for domain in VALID_FACEBOOK_DOMAINS):
            return SUBPROCESS_TIMEOUT_FACEBOOK

        # Check if it's another valid domain
        if any(domain in parsed.netloc for domain in VALID_OTHER_DOMAINS):
            return SUBPROCESS_TIMEOUT_OTHER_SITES

        # Default to YouTube timeout for unknown domains
        return SUBPROCESS_TIMEOUT_YOUTUBE

    except urllib.error.URLError:
        # If parsing fails, abort
        raise ValueError(f"URL '{url}' cannot be parsed, aborting")
    # abort on any other exception


def validate_video_url(url: str) -> tuple[bool, str]:
    """
    Validate that the URL is a valid video streaming URL (YouTube or other supported sites).

    Args:
        url: The URL string to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - is_valid: True if URL is valid, False otherwise
            - error_message: Empty string if valid, error description if invalid
    """
    from urllib.parse import urlparse

    if not url or not url.strip():
        return False, 'URL cannot be empty'

    try:
        parsed = urlparse(url=url)

        # Check scheme
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid URL scheme '{parsed.scheme}'. Must be http or https"

        # Check domain using the centralized validation function
        if not is_valid_domain_url(url=url):
            return (False,
                    f"Invalid domain '{parsed.netloc}'. Must be a YouTube, Facebook or other supported video site URL")
        return True, ''

    except Exception as e:
        return False, f'Invalid URL format: {e}'


def get_video_info(yt_dlp_path: Path, url: str) -> dict:
    """Get video information using yt-dlp by requesting the meta-data as JSON, w/o download of the video."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=url)

    cmd = [
        str(yt_dlp_path),
        '--dump-json',
        '--no-download',
        sanitized_url
    ]

    # Add cookie arguments if configured via environment variable
    cookie_args = get_cookie_args()
    if cookie_args:
        cmd[1:1] = cookie_args

    logger.debug(f'Getting video info with timeout of {timeout} seconds')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)

        # Try to parse as single JSON object first
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            # If parsing fails due to multiple JSON objects (playlist), parse only the first one
            if 'Extra data' in str(e):
                logger.warning('Multiple JSON objects detected in yt-dlp output, parsing first object only')
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            continue
            # Re-raise if it's not an "Extra data" error or no valid JSON found
            raise

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {timeout} seconds for URL '{url}'")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'yt-dlp failed: {e.stderr}')
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse yt-dlp output for '{url}': {e}")


def is_playlist(url: str) -> bool:
    """Check if url is a playlist, w/o downloading.
    Using the yt-dlp Python library."""
    ydl_opts: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }

    # Add cookie configuration if environment variable is set
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if cookie_env:
        browser = 'chrome' if cookie_env.lower() == 'chrome' else 'firefox'
        ydl_opts['cookiesfrombrowser'] = (browser,)

    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:  # type: ignore[arg-type]
        try:
            info = ydl.extract_info(url=url, download=False)
            return info.get('webpage_url_basename') == 'playlist'  # type: ignore[typeddict-item]
        except Exception as e:
            logger.error(f"Failed to get video info for URL '{url}': {e}")
            return False


def get_chapter_count(ytdlp_exe: Path, playlist_url: str) -> int:
    """
    Get the number of chapters in a YouTube video using yt-dlp.

    Args:
        ytdlp_exe (Path): path to yt-dlp executable
        playlist_url (str): YouTube video URL

    Returns:
        int: Number of chapters (0 if none or error)
    """
    timeout = 1000  # to avoid linter warning

    try:
        # Security: Validate URL before passing to subprocess
        sanitized_url = sanitize_url_for_subprocess(url=playlist_url)

        # Get appropriate timeout based on URL domain
        timeout = get_timeout_for_url(url=playlist_url)

        cmd = [ytdlp_exe, '--dump-json', '--no-download', sanitized_url]

        # Add cookie arguments if configured via environment variable
        cookie_args = get_cookie_args()
        if cookie_args:
            cmd[1:1] = cookie_args

        logger.debug(f'Getting chapter count with timeout of {timeout} seconds')
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)

        # Try to parse as single JSON object first
        try:
            video_info = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            # If parsing fails due to multiple JSON objects (playlist), parse only the first one
            if 'Extra data' in str(e):
                logger.warning('Multiple JSON objects detected in yt-dlp output, parsing first object only')
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            video_info = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
                else:
                    # No valid JSON found
                    raise
            else:
                # Re-raise if it's not an "Extra data" error
                raise

        chapters = video_info.get('chapters')
        # Handle cases where chapters is None or not a list
        if not chapters:
            return 0
        return len(chapters)
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp timed out after {timeout} seconds for URL '{playlist_url}'")
        return 0
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to get chapter count for URL '{playlist_url}': {e.stderr}")
        return 0
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse video info JSON for URL '{playlist_url}': {e}")
        return 0
    except (KeyError, TypeError) as e:
        logger.debug(f'No chapters found in video info: {e}')
        return 0


def display_chapters_and_confirm(video_info: dict) -> bool:
    """
    Display chapter list with timing information and prompt user for confirmation.

    Args:
        video_info: Video information dictionary from yt-dlp

    Returns:
        bool: True to continue, False to abort
    """
    chapters = video_info.get('chapters', [])
    if not chapters:
        return True  # No chapters to display, continue

    video_title = video_info.get('title', 'Unknown')
    video_duration = video_info.get('duration', 0)

    print('\n' + '='*80)
    print(f"Video: {video_title}")
    print(f'Total duration: {_format_duration(seconds=video_duration)}')
    print(f'Found {len(chapters)} chapters:')
    print('='*80)
    print('NOTE: Video chapters are cut at the nearest keyframe (I-frame) for clean splits.')
    print('      This may result in slightly longer durations than shown below.')
    print('      Audio chapters will match the exact times shown.')
    print('='*80)
    print(f"{'#':<4} {'Chapter Name':<50} {'Start':<10} {'End':<10} {'Duration':<10}")
    print('-'*80)

    for i, chapter in enumerate(chapters, 1):
        title = chapter.get('title', f'Chapter {i}')
        start_time = chapter.get('start_time', 0)
        end_time = chapter.get('end_time', video_duration)

        # Calculate duration
        duration = end_time - start_time

        # Format times
        start_str = _format_duration(seconds=start_time)
        end_str = _format_duration(seconds=end_time)
        duration_str = _format_duration(seconds=duration)

        # Truncate title if too long
        display_title = title[:47] + '...' if len(title) > 50 else title

        print(f'{i:<4} {display_title:<50} {start_str:<10} {end_str:<10} {duration_str:<10}')

    print('='*80)

    # Auto-continue without prompting
    return True


def create_chapters_csv(video_info: dict, output_dir: str, video_title: str) -> None:
    """
    Create a CSV file with chapter information instead of downloading video chapters.

    Args:
        video_info: Dictionary containing video metadata including chapters
        output_dir: Directory where CSV file should be saved
        video_title: Video title to use in CSV filename
    """
    chapters = video_info.get('chapters', [])
    if not chapters:
        logger.warning('No chapters found in video info')
        return

    # Use fixed filename
    csv_filename = 'segments-hms-full.txt'
    csv_path = Path(output_dir) / csv_filename

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f'Creating chapters CSV file: {csv_path}')

    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Write header with new column format
        writer.writerow([
            'start time',
            'end time',
            'song name',
            'original song name',
            'artist name',
            'album name',
            'year',
            'composer',
            'comments'
        ])

        # Write comment lines with video metadata
        uploader = video_info.get('uploader', '')
        video_url = video_info.get('webpage_url', '')

        writer.writerow([f"# Title: '{video_title}'"])
        writer.writerow([f"# Artist/Uploader: '{uploader}'"])
        writer.writerow([f'# URL: {video_url}'])

        # Extract year from video date if available
        year = ''
        upload_date = video_info.get('upload_date', '')
        if upload_date:
            # upload_date is typically in YYYYMMDD format
            year = upload_date[:4] if len(upload_date) >= 4 else ''

        # Write chapter data
        for chapter in chapters:
            start_seconds = chapter.get('start_time', 0)
            end_seconds = chapter.get('end_time', 0)
            title = chapter.get('title', '')

            # Convert seconds to HHMMSS format
            start_time = _seconds_to_hhmmss(seconds=start_seconds)
            end_time = _seconds_to_hhmmss(seconds=end_seconds)

            # Write row with empty fields for user to fill in later
            writer.writerow([
                start_time,                # start time
                end_time,                  # end time
                title,                     # song name
                '',                        # original song name (empty for user to fill)
                '',                        # artist name (empty for user to fill)
                '',                        # album name (empty for user to fill)
                year,                      # year (from video upload date if available)
                '',                        # composer (empty for user to fill)
                ''                         # comments (empty for user to fill)
            ])

    logger.info(f'Chapters CSV created successfully: {csv_path}')
    print(f'\nChapters CSV file created: {csv_path}')
