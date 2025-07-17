"""Misc. utility functions for yt-dlp scripts."""
import re
import unicodedata
import shutil
from pathlib import Path
import subprocess
import json
from typing import Dict, Any
import yt_dlp

# Greek strings handling, for file names and MP3 titles

# Regex: remove leading non-alphanumeric characters (English+Greek+Hebrew), including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF\u05d0-\u05ea]+')

def sanitize_string(dirty_string: str) -> str:
    """
    Remove leading unwanted characters (including spaces) from string.
    See the comment above 'pattern'.
    """
    return pattern.sub('', dirty_string)

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
    Move all MP3 files to 'yt-audio' subfolder and all MP4 files to 'yt-videos' subfolder.
    Creates the subfolders if they don't exist.

    Returns:
        dict: Summary of moved files with counts and any errors
    """
    current_dir = Path.cwd()

    moved_files = {'mp3': [], 'mp4': [], 'errors': []}

    # Find and move MP3 files
    for mp3_file in current_dir.glob('*.mp3'):
        try:
            destination = audio_dir / mp3_file.name
            shutil.move(str(mp3_file), str(destination))
            moved_files['mp3'].append(mp3_file.name)
            print(f"Moved {mp3_file.name} -> yt-audio/")
        except Exception as e:
            error_msg = f"Error moving {mp3_file.name}: {str(e)}"
            moved_files['errors'].append(error_msg)
            print(error_msg)

    # Find and move MP4 files
    for mp4_file in current_dir.glob('*.mp4'):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
            print(f"Moved {mp4_file.name} -> yt-videos/")
        except Exception as e:
            error_msg = f"Error moving {mp4_file.name}: {str(e)}"
            moved_files['errors'].append(error_msg)
            print(error_msg)

    # Print summary
    print(f"\nSummary:")
    print(f"MP3 files moved: {len(moved_files['mp3'])}")
    print(f"MP4 files moved: {len(moved_files['mp4'])}")
    if moved_files['errors']:
        print(f"Errors: {len(moved_files['errors'])}")
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

    moved_files = {'mp3': [], 'mp4': [], 'errors': []}

    # Move MP3 files
    for mp3_file in current_dir.glob('*.mp3'):
        try:
            destination = audio_dir / mp3_file.name
            shutil.move(str(mp3_file), str(destination))
            moved_files['mp3'].append(mp3_file.name)
        except Exception as e:
            moved_files['errors'].append(f"Error moving {mp3_file.name}: {str(e)}")

    # Move MP4 files
    for mp4_file in current_dir.glob('*.mp4'):
        try:
            destination = video_dir / mp4_file.name
            shutil.move(str(mp4_file), str(destination))
            moved_files['mp4'].append(mp4_file.name)
        except Exception as e:
            moved_files['errors'].append(f"Error moving {mp4_file.name}: {str(e)}")

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
                    print(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    print(f"Skipped (target exists): '{new_name}'")
    print(f"Renamed {ctr} files in folder '{folder_path}'")

# Video files utils

def get_video_info(yt_dlp_path: Path, url: str) -> Dict[str, Any]:
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
        raise RuntimeError(f"yt-dlp failed: {e.stderr}")
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
            print(f"Error: failed to get video info {e}")
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
    except:
        return 0
