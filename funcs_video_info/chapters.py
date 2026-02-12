"""Chapter detection, display, and CSV generation utilities."""
import csv
import json
import logging
import subprocess
from pathlib import Path

from funcs_utils import get_cookie_args, sanitize_string, sanitize_url_for_subprocess
from funcs_video_info.url_validation import get_timeout_for_url

logger = logging.getLogger(__name__)

_MAX_NAME_WITHOUT_EXT = 59  # 64 max total - 1 dot - 4 chars for longest ext (.flac)
_MAX_CHAPTER_TITLE_LEN = 53  # _MAX_NAME_WITHOUT_EXT - 6 chars for ' - NNN' suffix


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


def _build_filename_mapping(video_info: dict) -> dict[int, str]:
    """Build mapping of chapter numbers to normalized filenames without extension.

    Key 0 is the base video title. Keys 1..N are chapter titles with ' - NNN' suffix.
    Values are sanitized and truncated to fit within filename length limits.
    """
    video_title = video_info.get('title', 'Unknown')
    chapters = video_info.get('chapters', [])

    base_name = sanitize_string(dirty_string=video_title) or 'Unknown'
    if len(base_name) > _MAX_NAME_WITHOUT_EXT:
        base_name = base_name[:_MAX_NAME_WITHOUT_EXT].rstrip()
    mapping = {0: base_name}

    for i, chapter in enumerate(chapters, 1):
        title = chapter.get('title', f'Chapter {i}')
        sanitized = sanitize_string(dirty_string=title) or f'Chapter {i}'
        if len(sanitized) > _MAX_CHAPTER_TITLE_LEN:
            sanitized = sanitized[:_MAX_CHAPTER_TITLE_LEN].rstrip()
        mapping[i] = f'{sanitized} - {i:03d}'

    return mapping


def get_chapter_count(ytdlp_exe: Path, playlist_url: str, video_download_timeout: int | None = None) -> int:
    """
    Get the number of chapters in a YouTube video using yt-dlp.

    Args:
        ytdlp_exe (Path): path to yt-dlp executable
        playlist_url (str): YouTube video URL
        video_download_timeout (int | None): Optional timeout override in seconds

    Returns:
        int: Number of chapters (0 if none or error)
    """
    timeout = 1000  # to avoid linter warning

    try:
        # Security: Validate URL before passing to subprocess
        sanitized_url = sanitize_url_for_subprocess(url=playlist_url)

        # Get appropriate timeout based on URL domain
        timeout = get_timeout_for_url(url=playlist_url, video_download_timeout=video_download_timeout)

        cmd: list[str | Path] = [ytdlp_exe, '--dump-json', '--no-download', sanitized_url]

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


def display_chapters_and_confirm(video_info: dict) -> dict[int, str]:
    """
    Display chapter list with timing information and build filename mapping.

    Args:
        video_info: Video information dictionary from yt-dlp

    Returns:
        dict[int, str]: Mapping of chapter numbers to normalized filenames (without extension).
                        Empty dict if no chapters found.
    """
    chapters = video_info.get('chapters', [])
    if not chapters:
        return {}  # No chapters to display

    video_title = video_info.get('title', 'Unknown')
    video_duration = video_info.get('duration', 0)

    print('\n' + '='*80)
    print(f"Video: '{video_title}'")
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

    # Build and print filename mapping
    mapping = _build_filename_mapping(video_info=video_info)
    print('\n' + '='*80)
    print('Filename Mapping:')
    print('='*80)
    print(f"{'#':<4} {'Original Name':<50} {'Normalized Name'}")
    print('-'*80)
    for num in sorted(mapping.keys()):
        orig = video_title if num == 0 else chapters[num - 1].get('title', f'Chapter {num}')
        orig_display = orig[:47] + '...' if len(orig) > 50 else orig
        print(f'{num:<4} {orig_display:<50} {mapping[num]}')
    print('='*80)

    return mapping


def create_chapters_csv(video_info: dict, output_dir: Path | str, video_title: str) -> None:
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

    logger.info(f"Creating chapters CSV file: '{csv_path}'")

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

        # Write comment lines directly (bypassing csv.writer, which would
        # quote any line whose content contains a comma)
        uploader = video_info.get('uploader', '')
        video_url = video_info.get('webpage_url', '')

        csvfile.write(f"# Title: '{video_title}'\n")
        csvfile.write(f"# Artist/Uploader: '{uploader}'\n")
        csvfile.write(f'# URL: {video_url}\n')

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

    logger.info(f"Chapters CSV was created successfully: '{csv_path}'")
