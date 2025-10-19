"""Misc. utility functions for yt-dlp scripts."""
import re
import unicodedata
import shutil
import logging
from pathlib import Path
import subprocess
import json
import yt_dlp
import emoji
import urllib.error

from project_defs import (
    VALID_YOUTUBE_DOMAINS, VALID_FACEBOOK_DOMAINS, VALID_OTHER_DOMAINS,
    LEADING_NONALNUM_PATTERN, MULTIPLE_SPACES_PATTERN,
    GLOB_MP3_FILES, GLOB_M4A_FILES, GLOB_FLAC_FILES,
    GLOB_MP3_FILES_UPPER, GLOB_M4A_FILES_UPPER, GLOB_FLAC_FILES_UPPER, GLOB_MP4_FILES,
    SUBPROCESS_TIMEOUT_YOUTUBE, SUBPROCESS_TIMEOUT_FACEBOOK, SUBPROCESS_TIMEOUT_OTHER_SITES
)

logger = logging.getLogger(__name__)


# Security helper functions for subprocess calls

def sanitize_url_for_subprocess(url: str) -> str:
    """
    Sanitize URL before passing to subprocess (defense in depth).
    Even though we use list format (not shell=True), we validate
    that URLs don't contain shell metacharacters as an extra safety measure.

    Note: Ampersand (&) is NOT blocked because:
    - It's commonly used in YouTube URLs for query parameters (?v=xxx&t=10s)
    - With subprocess list format (not shell=True), & is just a regular character
    - It does NOT enable command chaining when using subprocess.run([cmd, arg1, arg2])

    Args:
        url: The URL to sanitize

    Returns:
        The original URL if safe

    Raises:
        ValueError: If URL contains suspicious characters
    """
    # Shell metacharacters that should never appear in a URL
    # Note: & is intentionally excluded - it's safe with list format and common in URLs
    shell_metacharacters = {'|', ';', '$', '`', '\n', '\r', '<', '>'}

    if any(char in url for char in shell_metacharacters):
        raise ValueError(f'URL contains suspicious shell metacharacters: {url}')

    return url

def validate_file_path_security(file_path: Path, expected_parent: Path | None = None) -> None:
    """
    Validate that a file path is safe to use in subprocess calls.
    Checks for path traversal attempts and ensures path is within expected directory.

    Args:
        file_path: Path to validate
        expected_parent: Optional parent directory that file_path should be within

    Raises:
        ValueError: If path is suspicious or outside expected parent
    """
    try:
        # Resolve to absolute path to detect '..' traversal
        resolved_path = file_path.resolve()

        # If expected parent provided, ensure file is within it
        if expected_parent:
            expected_parent_resolved = expected_parent.resolve()
            if not str(resolved_path).startswith(str(expected_parent_resolved)):
                raise ValueError(f'Path {file_path} is outside expected directory {expected_parent}')

    except (OSError, RuntimeError) as e:
        raise ValueError(f'Invalid or suspicious file path {file_path}: {e}')

# Greek strings handling, for file names and MP3 titles

# Regex: remove leading non-alphanumeric characters (English+Greek+Hebrew), including spaces
pattern = re.compile(LEADING_NONALNUM_PATTERN)

def sanitize_string(dirty_string: str) -> str:
    """
    Sanitize filename by:
    1. Replacing emojis with spaces
    2. Replacing foreign characters (not English/French/Greek/Hebrew) with spaces
    3. Removing leading unwanted characters and spaces
    4. Compressing multiple spaces into one
    5. Removing trailing spaces before file extension
    """
    if not dirty_string:
        return dirty_string

    # Split filename and extension
    if '.' in dirty_string:
        name_part, extension = dirty_string.rsplit('.', 1)
        has_extension = True
    else:
        name_part = dirty_string
        extension = ''
        has_extension = False

    # 1. Replace all emojis with spaces
    name_part = emoji.replace_emoji(name_part, replace=' ')

    # 2. Replace foreign characters with spaces
    # Keep: English (a-z, A-Z), French (àáâãäåæçèéêëìíîïðñòóôõöøùúûüýÿ),
    #       Greek (α-ω, Α-Ω), Hebrew (א-ת), numbers (0-9), and common punctuation
    allowed_chars = []
    for char in name_part:
        # English letters and numbers
        if char.isascii() and (char.isalnum() or char in ' .,;:!?()-_[]{}'):
            allowed_chars.append(char)
        # Greek letters (main range)
        elif '\u0370' <= char <= '\u03FF':
            allowed_chars.append(char)
        # Hebrew letters
        elif '\u05d0' <= char <= '\u05ea':
            allowed_chars.append(char)
        # French accented characters (Latin-1 Supplement)
        elif '\u00c0' <= char <= '\u00ff':
            allowed_chars.append(char)
        # Additional French characters in Latin Extended-A
        elif char in 'ĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁłŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž':
            allowed_chars.append(char)
        else:
            # Replace foreign character with space
            allowed_chars.append(' ')

    name_part = ''.join(allowed_chars)

    # 3. Remove leading unwanted characters (using existing pattern)
    name_part = pattern.sub('', name_part)

    # 4. Compress multiple spaces into one
    name_part = re.sub(MULTIPLE_SPACES_PATTERN, ' ', name_part)

    # 5. Remove leading and trailing spaces
    name_part = name_part.strip()

    # Reconstruct filename
    if has_extension and name_part:
        return f'{name_part}.{extension}'
    elif has_extension:
        # If name_part is empty, but we had an extension, keep the extension
        return f'untitled.{extension}'
    else:
        return name_part

def remove_diacritics(text: str) -> str:
    """
    Remove diacritics from Greek text by normalizing to NFD form
    and filtering out combining characters (diacritical marks).
    """
    # Normalize to NFD (decomposed form)
    normalized = unicodedata.normalize('NFD', text)
    # Filter out combining characters (diacritics)
    without_diacritics = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'
    )
    return without_diacritics

def greek_search(big_string: str, sub_string: str) -> bool:
    """
    Check if sub_string appears in big_string (case-insensitive), ignoring Greek diacritics (=letters with accents).

    Args:
        big_string (str): The string to search in
        sub_string (str): The string to search for

    Returns:
        bool: True if sub_string_x is found in big_string_x (ignoring diacritics), False otherwise
    """
    # Remove diacritics from both strings
    big_string_clean = remove_diacritics(text=big_string)
    sub_string_clean = remove_diacritics(text=sub_string)

    # Convert to lowercase for case-insensitive search
    big_string_clean = big_string_clean.lower()
    sub_string_clean = sub_string_clean.lower()

    # Check if sub_string appears in big_string
    return sub_string_clean in big_string_clean

# File utilities

def organize_media_files(video_dir: Path, audio_dir: Path) -> dict:
    """
    Move all MP3/M4A/FLAC files to 'yt-audio' subfolder and all MP4 files to 'yt-videos' subfolder.
    Creates the subfolders if they don't exist.

    Returns:
        dict: Summary with moved files counts, any errors, and original_names mapping.
              original_names maps final_path -> original_filename_before_move
    """
    current_dir = Path.cwd()

    moved_files = {'mp3': [], 'mp4': [], 'm4a': [], 'flac': [], 'errors': [], 'original_names': {}}

    # Get all audio-like files including case variations
    audio_files = (list(current_dir.glob(GLOB_MP3_FILES)) +
                   list(current_dir.glob(GLOB_M4A_FILES)) +
                   list(current_dir.glob(GLOB_FLAC_FILES)) +
                   list(current_dir.glob(GLOB_MP3_FILES_UPPER)) +
                   list(current_dir.glob(GLOB_M4A_FILES_UPPER)) +
                   list(current_dir.glob(GLOB_FLAC_FILES_UPPER)))

    # Find and move MP3/M4A/FLAC files to their respective subfolders
    for audio_file in audio_files:
        try:
            if audio_file.suffix.lower() == '.mp3':
                subfolder = audio_dir / 'mp3'
                moved_files['mp3'].append(audio_file.name)
                subfolder_name = 'mp3'
            elif audio_file.suffix.lower() == '.m4a':
                subfolder = audio_dir / 'm4a'
                moved_files['m4a'].append(audio_file.name)
                subfolder_name = 'm4a'
            elif audio_file.suffix.lower() == '.flac':
                subfolder = audio_dir / 'flac'
                moved_files['flac'].append(audio_file.name)
                subfolder_name = 'flac'
            else:
                # Skip files that are not MP3, M4A, or FLAC
                logger.warning(
                    f"Skipping unsupported audio file '{audio_file.name}' with extension '{audio_file.suffix}'")
                continue

            # Create subfolder if it doesn't exist
            subfolder.mkdir(parents=True, exist_ok=True)

            # Store original filename before moving
            original_name = audio_file.name
            destination = subfolder / audio_file.name
            shutil.move(str(audio_file), str(destination))
            # Map destination path to original name
            moved_files['original_names'][str(destination)] = original_name
            logger.info(f'Moved {audio_file.name} -> yt-audio/{subfolder_name}/')
        except Exception as e:
            error_msg = f'Error moving {audio_file.name}: {str(e)}'
            moved_files['errors'].append(error_msg)
            logger.error(error_msg)

    # Find and move MP4 files
    for mp4_file in current_dir.glob(GLOB_MP4_FILES):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
            logger.info(f'Moved {mp4_file.name} -> yt-videos/')
        except Exception as e:
            error_msg = f'Error moving {mp4_file.name}: {str(e)}'
            moved_files['errors'].append(error_msg)
            logger.error(error_msg)

    # Print summary
    logger.info('Summary:')
    logger.info(f'MP3 files moved: {len(moved_files["mp3"])}')
    logger.info(f'M4A files moved: {len(moved_files["m4a"])}')
    logger.info(f'FLAC files moved: {len(moved_files["flac"])}')
    logger.info(f'MP4 files moved: {len(moved_files["mp4"])}')
    if moved_files['errors']:
        logger.warning(f'Errors: {len(moved_files["errors"])}')
    return moved_files

def organize_media_files_silent() -> dict:
    """
    Same as organize_media_files() but without print statements.
    Returns only the summary dictionary.
    """
    current_dir = Path('.')
    audio_dir = current_dir / 'yt-audio'
    video_dir = current_dir / 'yt-videos'

    # Create directories if they don't exist
    audio_dir.mkdir(exist_ok=True)
    video_dir.mkdir(exist_ok=True)

    moved_files = {'mp3': [], 'mp4': [], 'm4a': [], 'errors': []}

    audio_files = list(current_dir.glob(GLOB_MP3_FILES)) + list(current_dir.glob(GLOB_M4A_FILES))

    # Move MP3 files
    for audio_file in audio_files:
        try:
            destination = audio_dir / audio_file.name
            shutil.move(str(audio_file), str(destination))
            if audio_file.suffix == 'mp3':
                moved_files['mp3'].append(audio_file.name)
            else:
                moved_files['m4a'].append(audio_file.name)
        except Exception as e:
            moved_files['errors'].append(f'Error moving {audio_file.name}: {str(e)}')

    # Move MP4 files
    for mp4_file in current_dir.glob(GLOB_MP4_FILES):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
        except Exception as e:
            moved_files['errors'].append(f'Error moving {mp4_file.name}: {str(e)}')

    return moved_files

def sanitize_filenames_in_folder(folder_path: Path,
                                 original_names: dict[str, str] | None = None) -> dict[str, str]:
    """
    Sanitize file names in the folder by removing leading unwanted characters.

    Args:
        folder_path: Path to folder containing files to sanitize
        original_names: Optional mapping of current_path -> original_filename to preserve through renames

    Returns:
        dict mapping final_path -> original_ytdlp_filename (before any renames)
    """
    ctr = 0
    result_mapping = {}

    # Start with incoming mapping if provided
    if original_names:
        result_mapping.update(original_names)

    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = sanitize_string(dirty_string=file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    # Get the original filename for this file
                    old_path_str = str(file_path)
                    original_filename = result_mapping.get(old_path_str, file_path.name)

                    # Rename the file
                    file_path.rename(new_path)

                    # Update mapping: remove old path, add new path
                    if old_path_str in result_mapping:
                        del result_mapping[old_path_str]
                    result_mapping[str(new_path)] = original_filename

                    ctr += 1
                    logger.info(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    logger.warning(f"Skipped (target exists): '{new_name}'")
                    # Keep the existing mapping for this file
                    old_path_str = str(file_path)
                    if old_path_str in result_mapping:
                        result_mapping[old_path_str] = result_mapping[old_path_str]
            else:
                # No rename needed, but preserve mapping if it exists
                file_path_str = str(file_path)
                if file_path_str not in result_mapping:
                    result_mapping[file_path_str] = file_path.name

    logger.info(f"Renamed {ctr} files in folder '{folder_path}'")
    return result_mapping

# Video files utils

def get_timeout_for_url(url: str, other_sites_timeout: int | None = None) -> int:
    """
    Determine the appropriate subprocess timeout based on the URL domain.

    Args:
        url: The URL to check
        other_sites_timeout: Optional timeout in seconds for other sites (non-YouTube/Facebook).
                           If None, uses SUBPROCESS_TIMEOUT_OTHER_SITES default.

    Returns:
        int: Timeout in seconds (300 for YouTube & Facebook, 3600 for other sites by default)
    """
    from urllib.parse import urlparse

    # Use default if not provided
    if other_sites_timeout is None:
        other_sites_timeout = SUBPROCESS_TIMEOUT_OTHER_SITES

    try:
        parsed = urlparse(url)

        # Check if it's a YouTube or Facebook domain
        if any(domain in parsed.netloc for domain in VALID_YOUTUBE_DOMAINS):
            return SUBPROCESS_TIMEOUT_YOUTUBE

        if any(domain in parsed.netloc for domain in VALID_FACEBOOK_DOMAINS):
            return SUBPROCESS_TIMEOUT_FACEBOOK

        # Check if it's another valid domain
        if any(domain in parsed.netloc for domain in VALID_OTHER_DOMAINS):
            return other_sites_timeout

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

        # Check domain - accept both YouTube and other valid domains
        all_valid_domains = VALID_YOUTUBE_DOMAINS + VALID_FACEBOOK_DOMAINS + VALID_OTHER_DOMAINS
        if not any(domain in parsed.netloc for domain in all_valid_domains):
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
    logger.debug(f'Getting video info with timeout of {timeout} seconds')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {timeout} seconds for URL '{url}'")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'yt-dlp failed: {e.stderr}')
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse yt-dlp output for '{url}': {e}")

def is_playlist(url: str) -> bool:
    """Check if url is a playlist, w/o downloading.
    Using the yt-dlp Python library."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url=url, download=False)
            return info.get('webpage_url_basename') == 'playlist'
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
    try:
        # Security: Validate URL before passing to subprocess
        sanitized_url = sanitize_url_for_subprocess(url=playlist_url)

        # Get appropriate timeout based on URL domain
        timeout = get_timeout_for_url(url=playlist_url)

        cmd = [ytdlp_exe, '--dump-json', '--no-download', sanitized_url]
        logger.debug(f'Getting chapter count with timeout of {timeout} seconds')
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        video_info = json.loads(result.stdout)
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
