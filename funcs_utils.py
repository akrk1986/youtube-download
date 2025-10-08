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

from project_defs import VALID_YOUTUBE_DOMAINS

logger = logging.getLogger(__name__)

# Greek strings handling, for file names and MP3 titles

# Regex: remove leading non-alphanumeric characters (English+Greek+Hebrew), including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF\u05d0-\u05ea]+')

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
    name_part = re.sub(r'\s+', ' ', name_part)

    # 5. Remove leading and trailing spaces
    name_part = name_part.strip()

    # Reconstruct filename
    if has_extension and name_part:
        return f'{name_part}.{extension}'
    elif has_extension:
        # If name_part is empty but we had an extension, keep the extension
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
    Move all MP3/M4A files to 'yt-audio' subfolder and all MP4 files to 'yt-videos' subfolder.
    Creates the subfolders if they don't exist.

    Returns:
        dict: Summary of moved files with counts and any errors
    """
    current_dir = Path.cwd()

    moved_files = {'mp3': [], 'mp4': [], 'm4a': [], 'errors': []}

    # Get all audio-like files including case variations
    audio_files = (list(current_dir.glob('*.mp3')) +
                   list(current_dir.glob('*.m4a')) +
                   list(current_dir.glob('*.MP3')) +
                   list(current_dir.glob('*.M4A')))

    # Find and move MP3/M4A files to their respective subfolders
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
            else:
                # Skip files that are not MP3 or M4A
                logger.warning(f'Skipping unsupported audio file type: {audio_file.name} (extension: {audio_file.suffix})')
                continue

            # Create subfolder if it doesn't exist
            subfolder.mkdir(parents=True, exist_ok=True)

            destination = subfolder / audio_file.name
            shutil.move(str(audio_file), str(destination))
            logger.info(f'Moved {audio_file.name} -> yt-audio/{subfolder_name}/')
        except Exception as e:
            error_msg = f'Error moving {audio_file.name}: {str(e)}'
            moved_files['errors'].append(error_msg)
            logger.error(error_msg)

    # Find and move MP4 files
    for mp4_file in current_dir.glob('*.mp4'):
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

    audio_files = list(current_dir.glob('*.mp3')) + list(current_dir.glob('*.m4a'))

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
    for mp4_file in current_dir.glob('*.mp4'):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
        except Exception as e:
            moved_files['errors'].append(f'Error moving {mp4_file.name}: {str(e)}')

    return moved_files

def sanitize_filenames_in_folder(folder_path: Path) -> None:
    """Sanitize file names in the folder by removing leading unwanted characters."""
    ctr = 0
    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = sanitize_string(dirty_string=file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    file_path.rename(new_path)
                    ctr += 1
                    logger.info(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    logger.warning(f"Skipped (target exists): '{new_name}'")
    logger.info(f"Renamed {ctr} files in folder '{folder_path}'")

# Video files utils

def validate_youtube_url(url: str) -> tuple[bool, str]:
    """
    Validate that the URL is a valid YouTube URL.

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
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid URL scheme '{parsed.scheme}'. Must be http or https"

        # Check domain
        if not any(domain in parsed.netloc for domain in VALID_YOUTUBE_DOMAINS):
            return False, f"Invalid domain '{parsed.netloc}'. Must be a YouTube URL"

        return True, ''

    except Exception as e:
        return False, f'Invalid URL format: {e}'

def get_video_info(yt_dlp_path: Path, url: str) -> dict[str, any]:
    """Get video information using yt-dlp by requesting the meta-data as JSON, w/o download of the video."""
    cmd = [
        str(yt_dlp_path),
        '--dump-json',
        '--no-download',
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
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
            logger.error(f'Error: failed to get video info {e}')
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
        cmd = [ytdlp_exe, '--dump-json', '--no-download', playlist_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        chapters = video_info.get('chapters', [])
        return len(chapters)
    except subprocess.CalledProcessError as e:
        logger.warning(f'Failed to get video info for chapter count: {e.stderr}')
        return 0
    except json.JSONDecodeError as e:
        logger.warning(f'Failed to parse video info JSON: {e}')
        return 0
    except (KeyError, TypeError) as e:
        logger.debug(f'No chapters found in video info: {e}')
        return 0
