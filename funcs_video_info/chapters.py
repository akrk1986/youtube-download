"""Chapter detection, display, and CSV generation utilities."""
import csv
import json
import logging
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from funcs_utils import get_cookie_args, sanitize_string, sanitize_url_for_subprocess
from funcs_video_info.metadata import get_video_info
from funcs_video_info.url_validation import get_timeout_for_url
from project_defs import NUMBERED_TRACKLIST_PATTERN

logger = logging.getLogger(__name__)

_MAX_NAME_WITHOUT_EXT = 59  # 64 max total - 1 dot - 4 chars for longest ext (.flac)
_MAX_CHAPTER_TITLE_LEN = 53  # _MAX_NAME_WITHOUT_EXT - 6 chars for ' - NNN' suffix
_MIN_NUMBERED_TRACKLIST_ROWS = 2  # below this, treat the description as not a tracklist
_NUMBERED_TRACKLIST_RE = re.compile(NUMBERED_TRACKLIST_PATTERN, re.MULTILINE)


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


# Leading track sequence, e.g. '01. ', '1.', '12.  ' at the start of a song title.
_LEADING_SEQUENCE_RE = re.compile(r'^\s*\d+\.\s*')
# Any trailing run of whitespace and periods (e.g. 'Title.', 'Title...').
_TRAILING_PERIODS_RE = re.compile(r'[\s.]+$')


def _clean_song_title(title: str) -> str:
    """Strip a leading track-sequence number and trailing periods from a song title.

    Removes a leading 'NN. ' / 'N.' sequence (as used in tracklists) and any
    trailing period(s), so 'NN. Song Title...' becomes 'Song Title'.

    Args:
        title: Raw chapter/song title.

    Returns:
        str: The title without the leading sequence number or trailing periods.
    """
    cleaned = _LEADING_SEQUENCE_RE.sub('', title)
    return _TRAILING_PERIODS_RE.sub('', cleaned)


def _hms_to_seconds(time_str: str) -> int:
    """Convert a 'MM:SS' or 'HH:MM:SS' timestamp to seconds."""
    parts = [int(p) for p in time_str.split(':')]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _parse_numbered_tracklist(description: str, video_duration: float) -> list[dict[str, Any]]:
    """Parse a title-first numbered tracklist from a video description.

    Matches lines of the form 'NN. Title  START[ - END]' (leading number optional),
    taking the first timestamp on each line as the chapter start. Titles are cleaned
    with _clean_song_title(). End times are derived from the next row's start (the last
    row uses video_duration), so a malformed end range does not break parsing.

    Args:
        description: Full video description text.
        video_duration: Video duration in seconds (used for the last chapter's end).

    Returns:
        list[dict[str, Any]]: Chapters as dicts with 'start_time', 'end_time', 'title',
        in description order. Empty if no tracklist lines are found.
    """
    rows: list[dict[str, Any]] = []
    for title, time_str in _NUMBERED_TRACKLIST_RE.findall(description):
        clean_title = _clean_song_title(title.strip())
        if clean_title:
            rows.append({'start_time': _hms_to_seconds(time_str=time_str), 'title': clean_title})

    for i, row in enumerate(rows):
        row['end_time'] = rows[i + 1]['start_time'] if i + 1 < len(rows) else video_duration

    return rows


def _resolve_csv_chapters(video_info: dict[str, Any], chapter_source: str) -> list[dict[str, Any]]:
    """Choose the chapter list used to build the CSV based on the requested source.

    'manual' parses a numbered tracklist from the description; if none is found it warns
    and falls back to the native yt-dlp chapters. Any other value uses native chapters.

    Args:
        video_info: Video information dictionary from yt-dlp.
        chapter_source: 'manual' to parse the description, otherwise native chapters.

    Returns:
        list[dict[str, Any]]: The chapters to write to the CSV.
    """
    native = video_info.get('chapters') or []
    if chapter_source != 'manual':
        return native

    parsed = _parse_numbered_tracklist(description=video_info.get('description') or '',
                                       video_duration=video_info.get('duration') or 0)
    if len(parsed) >= _MIN_NUMBERED_TRACKLIST_ROWS:
        logger.info(f'Using {len(parsed)} chapters parsed from the description (manual mode)')
        return parsed

    logger.warning('manual mode found no numbered tracklist in the description; '
                   'using native yt-dlp chapters instead')
    return native


def _sanitize_chapter_title(title: str, max_len: int, fallback: str = '') -> str:
    """Sanitize and truncate a chapter/video title."""
    sanitized = (sanitize_string(dirty_string=title) or fallback).strip()
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len].rstrip()
    return sanitized


def _build_filename_mapping(video_info: dict[str, Any]) -> dict[int, str]:
    """Build mapping of chapter numbers to normalized filenames without extension.

    Key 0 is the base video title. Keys 1..N are chapter titles with ' - NNN' suffix.
    Values are sanitized and truncated to fit within filename length limits.
    """
    video_title = video_info.get('title', 'Unknown')
    chapters = video_info.get('chapters', [])

    base_name = _sanitize_chapter_title(video_title, _MAX_NAME_WITHOUT_EXT, fallback='Unknown')
    mapping = {0: base_name}

    for i, chapter in enumerate(chapters, 1):
        title = chapter.get('title', f'Chapter {i}')
        sanitized = _sanitize_chapter_title(_clean_song_title(title), _MAX_CHAPTER_TITLE_LEN,
                                            fallback=f'Chapter {i}')
        mapping[i] = f'{sanitized} - {i:03d}'

    return mapping


def get_chapter_count(ytdlp_exe: Path, playlist_url: str, video_download_timeout: int | None = None) -> int:
    """
    Get the number of chapters in a YouTube video using yt-dlp.

    Args:
        ytdlp_exe: path to yt-dlp executable
        playlist_url: YouTube video URL
        video_download_timeout: Optional timeout override in seconds

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
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, timeout=timeout
        )

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
                    logger.warning(f"Failed to parse video info JSON for URL '{playlist_url}': {e}")
                    return 0
            else:
                logger.warning(f"Failed to parse video info JSON for URL '{playlist_url}': {e}")
                return 0

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
    except (KeyError, TypeError) as e:
        logger.debug(f'No chapters found in video info: {e}')
        return 0


def display_chapters_and_confirm(video_info: dict[str, Any]) -> dict[int, str]:
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


def create_chapters_csv(video_info: dict[str, Any], output_dir: Path | str, video_title: str) -> None:
    """
    Create a CSV file with chapter information instead of downloading video chapters.

    The chapter source (native vs. description-parsed) is already resolved by
    detect_chapters, so this reads video_info['chapters'] directly.

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

    with csv_path.open('w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Write header with new column format
        writer.writerow([
            'start time',
            'album art timestamp',
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

        # Pre-compute sanitized song names to find repeats. A name that appears more than
        # once (e.g. recurring 'Συνέντευξη' interview breaks) is marked 'SKIP' in the comment
        # column for every occurrence, so the losslesscut-csv step skips those rows entirely.
        base_names = [_sanitize_chapter_title(_clean_song_title(ch.get('title', '')), 60)
                      for ch in chapters]
        name_totals = Counter(base_names)

        # Write chapter data
        seen_song_names: dict[str, int] = {}
        for i, chapter in enumerate(chapters):
            start_seconds = chapter.get('start_time', 0)
            end_seconds = chapter.get('end_time', 0)
            song_name = base_names[i]
            comment = 'SKIP' if name_totals[song_name] > 1 else ''

            # De-duplicate identical song names so they don't map to the same file:
            # the 2nd occurrence becomes 'name(01)', the 3rd 'name(02)', etc.
            seen_count = seen_song_names.get(song_name, 0)
            seen_song_names[song_name] = seen_count + 1
            if seen_count > 0:
                song_name = f'{song_name}({seen_count:02d})'

            # Convert seconds to HHMMSS format
            start_time = _seconds_to_hhmmss(seconds=start_seconds)
            end_time = _seconds_to_hhmmss(seconds=end_seconds)

            # First row carries the artist/album placeholders and the year; subsequent rows
            # use '-' so the value is not repeated down the column.
            artist_name = 'Artist-name' if i == 0 else '-'
            album_name = 'Album-name' if i == 0 else '-'
            year_cell = year if i == 0 else '-'

            writer.writerow([
                start_time,                # start time
                '',                        # album art timestamp (empty — LosslessCut-csv auto-selects)
                end_time,                  # end time
                song_name,                 # song name (sanitized, max 60 chars)
                '',                        # original song name (empty for user to fill)
                artist_name,               # artist name
                album_name,                # album name
                year_cell,                 # year (from video upload date; first row only)
                '',                        # composer (empty for user to fill)
                comment                    # comments ('SKIP' for repeated song names)
            ])

    logger.info(f"Chapters CSV was created successfully: '{csv_path}'")


def detect_chapters(
    yt_dlp_exe: str,
    video_url: str,
    video_download_timeout: int | None,
    url_is_playlist: bool,
    show_chapters: bool,
    chapter_source: str = 'json',
) -> tuple[bool, dict[str, Any] | None, str | None, str | None, dict[int, str]]:
    """Detect chapters and fetch video info if chapters exist.

    Args:
        yt_dlp_exe: Path to yt-dlp executable.
        video_url: Video URL to check.
        video_download_timeout: Timeout for video downloads in seconds.
        url_is_playlist: Whether the URL is a playlist.
        show_chapters: Whether to display chapters and build name map.
        chapter_source: 'manual' to use a numbered tracklist parsed from the description
            (safe here because manual mode never splits audio); otherwise native chapters.

    Returns:
        tuple[bool, dict[str, Any] | None, str | None, str | None, dict[int, str]]:
            (has_chapters, video_info, uploader_name, video_title, chapter_name_map)
    """
    if url_is_playlist:
        logger.info('URL is a playlist, not extracting chapters')
        return False, None, None, None, {}

    chapters_count = get_chapter_count(
        ytdlp_exe=Path(yt_dlp_exe),
        playlist_url=video_url,
        video_download_timeout=video_download_timeout,
    )
    has_chapters = chapters_count > 0
    if not has_chapters:
        return False, None, None, None, {}

    logger.info(f'Video has {chapters_count} native chapters')
    video_info = get_video_info(
        yt_dlp_path=Path(yt_dlp_exe),
        url=video_url,
        video_download_timeout=video_download_timeout,
    )
    # Resolve the chapter source once so the count, display, and CSV are consistent.
    video_info['chapters'] = _resolve_csv_chapters(video_info=video_info, chapter_source=chapter_source)
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
